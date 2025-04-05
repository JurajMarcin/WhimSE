/*
 * Copyright (C) 2025 Juraj Marcin <juraj@jurajmarcin.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

#include "cmp_set.h"

#include <assert.h>
#include <error.h>
#include <stdlib.h>
#include <string.h>

#include <sepol/policydb/hashtab.h>
#include <cil/cil.h>
#include <cil_tree.h>

#include "cmp_common.h"
#include "cmp_node.h"
#include "cmp_subset.h"
#include "diff.h"
#include "mem.h"
#include "utils.h"


struct set_finalize_args {
    size_t i;
    char *child_hashes;
};

static int set_finalize(hashtab_key_t key, hashtab_datum_t datum, void *opaque)
{
    (void)key;
    struct set_finalize_args *args = opaque;
    struct cmp_subset *subset = datum;

    cmp_subset_finalize(subset);

    memcpy(args->child_hashes + HASH_SIZE * args->i, subset->full_hash, HASH_SIZE);
    args->i++;
    return 0;
}

struct cmp_set *cmp_set_create(struct cil_tree_node *cl_head)
{
    struct cmp_set *set = mem_alloc(sizeof(*set));

    size_t child_count = 0;
    for (const struct cil_tree_node *cil_node = cl_head; cil_node; cil_node = cil_node->next) {
        child_count++;
    }
    if (!child_count) {
        set->items = NULL;
        cmp_hash(strlen("<empty-set>"), "<empty-set>", set->full_hash);
        return set;
    }
    set->items = hashtab_create(&cmp_hash_hashtab_hash, &cmp_hash_hashtab_cmp, child_count);
    mem_check(set->items);

    struct cil_tree_node *cil_node = cl_head;
    while (cil_node) {
        struct cmp_node *node = cmp_node_create(cil_node);
        cil_node = cil_node->next;
        struct cmp_subset *subset = hashtab_search(set->items, node->partial_hash);
        if (!subset) {
            subset = cmp_subset_create(node);
            char *partial_hash = mem_dup(node->partial_hash, HASH_SIZE);
            if (hashtab_insert(set->items, partial_hash, subset)) {
                error(EXIT_FAILURE, 0, "cmp_set_create: Failed to add subset to hashtab");
            }
        }
        cmp_subset_add_node(subset, node);
    }

    struct set_finalize_args finalize_args = {
        .child_hashes = mem_alloc(HASH_SIZE * set->items->nel),
    };
    hashtab_map(set->items, &set_finalize, &finalize_args);
    qsort(finalize_args.child_hashes, finalize_args.i, HASH_SIZE, &cmp_hash_qsort_cmp);

    cmp_hash(HASH_SIZE * finalize_args.i, finalize_args.child_hashes, set->full_hash);

    mem_free(finalize_args.child_hashes);
    return set;
}

struct set_compare_args {
    enum diff_side this_side;
    const struct cmp_set *other_set;
    struct diff_tree_node *diff_node;
};

static int set_compare_map(hashtab_key_t key, hashtab_datum_t datum, void *opaque)
{
    const char *subset_partial_hash = key;
    const struct cmp_subset *this_subset = datum;
    struct set_compare_args *args = opaque;

    const struct cmp_subset *other_subset = hashtab_search(MAYBE(args->other_set, items), subset_partial_hash);
    if (args->this_side == DIFF_LEFT) {
        cmp_subset_compare(this_subset, other_subset, args->diff_node);
    } else if (!other_subset) {
        // Compare from right to left only if not found on the left side
        cmp_subset_compare(NULL, this_subset, args->diff_node);
    }

    return 0;
}

void cmp_set_compare(struct cmp_set *left, struct cmp_set *right, struct diff_tree_node *diff_node)
{
    if (!cmp_hash_cmp(MAYBE(left, full_hash), MAYBE(right, full_hash))) {
        return;
    }
    struct set_compare_args args = {
        .this_side = DIFF_LEFT,
        .other_set = right,
        .diff_node = diff_node,
    };
    hashtab_map(MAYBE(left, items), &set_compare_map, &args);
    args = (struct set_compare_args){
        .this_side = DIFF_RIGHT,
        .other_set = left,
        .diff_node = diff_node,
    };
    hashtab_map(MAYBE(right, items), &set_compare_map, &args);
}

struct set_sim_args {
    enum diff_side this_side;
    const struct cmp_set *other_set;
    struct cmp_sim *sim;
};


static int set_sim_map(hashtab_key_t key, hashtab_datum_t datum, void *opaque)
{
    const char *subset_partial_hash = key;
    const struct cmp_subset *this_subset = datum;
    struct set_sim_args *args = opaque;

    const struct cmp_subset *other_subset = hashtab_search(MAYBE(args->other_set, items), subset_partial_hash);
    struct cmp_sim subset_sim;
    if (args->this_side == DIFF_LEFT) {
        subset_sim = cmp_subset_sim(this_subset, other_subset);
    } else if (!other_subset) {
        // Compare from right to left only if not found on the left side
        subset_sim = cmp_subset_sim(NULL, this_subset);
    }
    cmp_sim_add(args->sim, &subset_sim);

    return 0;
}

struct cmp_sim cmp_set_sim(const struct cmp_set *left, struct cmp_set *right)
{
    struct cmp_sim sim = { 0 };

    struct set_sim_args args = {
        .this_side = DIFF_LEFT,
        .other_set = right,
        .sim = &sim,
    };
    hashtab_map(MAYBE(left, items), &set_sim_map, &args);
    args = (struct set_sim_args){
        .this_side = DIFF_RIGHT,
        .other_set = left,
        .sim = &sim,
    };
    hashtab_map(MAYBE(right, items), &set_sim_map, &args);

    return sim;
}

static int set_detroy_map(hashtab_key_t key, hashtab_datum_t datum, void *opaque)
{
    (void)opaque;
    char *partial_hash = key;
    struct cmp_subset *subset = datum;
    mem_free(partial_hash);
    cmp_subset_destroy(subset);
    return 0;
}

void cmp_set_destroy(struct cmp_set *set)
{
    if (!set) {
        return;
    }
    hashtab_map(set->items, &set_detroy_map, NULL);
    hashtab_destroy(set->items);
    mem_free(set);
}
