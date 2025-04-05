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

#include "cmp_subset.h"

#include <assert.h>
#include <error.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include <cil_internal.h>
#include <sepol/errcodes.h>
#include <sepol/policydb/hashtab.h>

#include "cmp_common.h"
#include "cmp_node.h"
#include "cmp_subset_defs.h"
#include "diff.h"
#include "mem.h"
#include "utils.h"


struct cmp_subset *cmp_subset_create(const struct cmp_node *node)
{
    const struct cmp_subset_def *def = cmp_subset_get_def(node->cil_node->flavor);
    struct cmp_subset *subset = mem_alloc(sizeof(*subset));
    *subset = (struct cmp_subset) {
        .flavor = node->cil_node->flavor,
        .items = hashtab_create(&cmp_hash_hashtab_hash, &cmp_hash_hashtab_cmp, 10),
        .data = mem_alloc(def->data_size),
    };
    mem_check(subset->items);

    if (def->init) {
        def->init(subset);
    }

    return subset;
}

void cmp_subset_add_node(struct cmp_subset *subset, struct cmp_node *node)
{
    const struct cmp_subset_def *def = cmp_subset_get_def(subset->flavor);
    int rc = hashtab_insert(subset->items, node->full_hash, node);
    if (rc == SEPOL_EEXIST) {
        // const struct cmp_node *duplicate = hashtab_search(subset->items, node->full_hash);
        // error(0, 0, "cmp_subset_add_node: Found duplicate rule of type %d (%s) at line %d with rule at line %d", node->cil_node->flavor, cil_node_to_string(node->cil_node), node->cil_node->line, duplicate->cil_node->line);
        cmp_node_destroy(node);
        return;
    } else if (rc) {
        error(EXIT_FAILURE, 0, "cmp_subset_add_node: Failed to add node to hashtab");
    }
    if (def->add_node) {
        def->add_node(subset, node);
    }
}

static int finalize_copy_hashtab_map(hashtab_key_t key, hashtab_datum_t datum, void *opaque)
{
    hashtab_t hashtab = opaque;
    if (hashtab_insert(hashtab, key, datum)) {
        error(EXIT_FAILURE, 0, "cmp_subset_add_node: Failed to add node to hashtab");
    }
    return 0;
}

struct finalize_hash_children_args {
    size_t i;
    char *child_hashes;
};

static int finalize_hash_children_map(hashtab_key_t key, hashtab_datum_t datum, void *opaque)
{
    (void)datum;
    struct finalize_hash_children_args *args = opaque;

    memcpy(args->child_hashes + HASH_SIZE * args->i, key, HASH_SIZE);
    args->i++;
    return 0;
}

void cmp_subset_finalize(struct cmp_subset *subset)
{
    const struct cmp_subset_def *def = cmp_subset_get_def(subset->flavor);

    if (!def->finalize || !def->finalize(subset)) {
        hashtab_t hashtab = hashtab_create(&cmp_hash_hashtab_hash, &cmp_hash_hashtab_cmp, subset->items->nel);
        mem_check(hashtab);
        hashtab_map(subset->items, &finalize_copy_hashtab_map, hashtab);
        hashtab_destroy(subset->items);
        subset->items = hashtab;
        if (hashtab->nel == 1) {
            struct finalize_hash_children_args finalize_hash_children_args = {
                .child_hashes = subset->full_hash,
            };
            hashtab_map(subset->items, &finalize_hash_children_map, &finalize_hash_children_args);
        } else {
            struct finalize_hash_children_args finalize_hash_children_args = {
                .child_hashes = mem_alloc(HASH_SIZE * subset->items->nel),
            };
            hashtab_map(subset->items, &finalize_hash_children_map, &finalize_hash_children_args);
            qsort(finalize_hash_children_args.child_hashes, finalize_hash_children_args.i, HASH_SIZE, &cmp_hash_qsort_cmp);

            cmp_hash(HASH_SIZE * finalize_hash_children_args.i, finalize_hash_children_args.child_hashes, subset->full_hash);

            mem_free(finalize_hash_children_args.child_hashes);
        }
    }
}

struct subset_compare_args {
    enum diff_side this_side;
    const struct cmp_subset *other_side;
    struct diff_tree_node *diff_node;
};

static int subset_compare_map(hashtab_key_t key, hashtab_datum_t datum, void *opaque)
{
    (void)key;
    const struct cmp_node *this_node = datum;
    struct subset_compare_args *args = opaque;

    const struct cmp_node *other_node = hashtab_search(MAYBE(args->other_side, items), this_node->full_hash);
    if (!other_node) {
        diff_tree_append_diff(args->diff_node, args->this_side, this_node, NULL);
    }

    return 0;
}

void cmp_subset_compare(const struct cmp_subset *left, const struct cmp_subset *right, struct diff_tree_node *diff_node)
{
    if (!left && !right) {
        return;
    }
    assert(!left || !right || left->flavor == right->flavor);
    if (!cmp_hash_cmp(MAYBE(left, full_hash), MAYBE(right, full_hash))) {
        return;
    }
    const struct cmp_subset_def *def = cmp_subset_get_def(EITHER(left, right, flavor));
    if (def->compare) {
        def->compare(left, right, diff_node);
        return;
    }
    struct subset_compare_args args = {
        .this_side = DIFF_LEFT,
        .other_side = right,
        .diff_node = diff_node,
    };
    hashtab_map(MAYBE(left, items), &subset_compare_map, &args);
    args = (struct subset_compare_args) {
        .this_side = DIFF_RIGHT,
        .other_side = left,
        .diff_node = diff_node,
    };
    hashtab_map(MAYBE(right, items), &subset_compare_map, &args);
}

struct subset_sim_args {
    enum diff_side this_side;
    const struct cmp_subset *other_side;
    struct cmp_sim *sim;
};

static int subset_sim_map(hashtab_key_t key, hashtab_datum_t datum, void *opaque)
{
    (void)key;
    const struct cmp_node *this_node = datum;
    struct subset_sim_args *args = opaque;

    const struct cmp_node *other_node = hashtab_search(MAYBE(args->other_side, items), this_node->full_hash);
    if (other_node) {
        args->sim->common++;
    } else {
        switch (args->this_side) {
        case DIFF_LEFT:
            args->sim->left++;
            break;
        case DIFF_RIGHT:
            args->sim->right++;
            break;
        default:
            assert(false /* unreachable */);
        }
    }

    return 0;
}

struct cmp_sim cmp_subset_sim(const struct cmp_subset *left, const struct cmp_subset *right)
{
    if (!left && !right) {
        return (struct cmp_sim) { 0 };
    }
    assert(!left || !right || left->flavor == right->flavor);
    const struct cmp_subset_def *def = cmp_subset_get_def(EITHER(left, right, flavor));
    if (!cmp_hash_cmp(MAYBE(left, full_hash), MAYBE(right, full_hash))) {
        return (struct cmp_sim) { .common = left->items->nel };
    }
    if (def->sim) {
        return def->sim(left, right);
    }

    struct cmp_sim sim = { 0 };

    struct subset_sim_args args = {
        .this_side = DIFF_LEFT,
        .other_side = right,
        .sim = &sim,
    };
    hashtab_map(MAYBE(left, items), &subset_sim_map, &args);
    args = (struct subset_sim_args) {
        .this_side = DIFF_RIGHT,
        .other_side = left,
        .sim = &sim,
    };
    hashtab_map(MAYBE(right, items), &subset_sim_map, &args);

    return sim;
}

static int subset_destroy_map(hashtab_key_t key, hashtab_datum_t datum, void *opaque)
{
    (void)key; // key points to a static array inside datum struct
    (void)opaque;
    struct cmp_node *node = datum;
    cmp_node_destroy(node);
    return 0;
}

void cmp_subset_destroy(struct cmp_subset *subset)
{
    if (!subset) {
        return;
    }
    const struct cmp_subset_def *def = cmp_subset_get_def(subset->flavor);
    if (def->destroy) {
        def->destroy(subset);
    }
    hashtab_map(subset->items, &subset_destroy_map, NULL);
    hashtab_destroy(subset->items);
    mem_free(subset->data);
    mem_free(subset);
}
