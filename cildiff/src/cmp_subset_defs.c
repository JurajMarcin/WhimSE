#include "cmp_subset_defs.h"

#include <assert.h>

#include <sepol/policydb/hashtab.h>
#include <stdlib.h>
#include <string.h>

#include "cil_flavor.h"
#include "cmp_common.h"
#include "cmp_node.h"
#include "cmp_subset.h"
#include "diff.h"
#include "mem.h"
#include "utils.h"


#define DECLARE(name) \
    struct cmp_subset_ ## name
#define DECLARE_INIT(name) \
    static void cmp_subset_ ## name ## _init(struct cmp_subset *subset)
#define DECLARE_ADD_NODE(name) \
    static void cmp_subset_ ## name ## _add_node(struct cmp_subset *subset, struct cmp_node *node)
#define DECLARE_FINALIZE(name) \
    static bool cmp_subset_ ## name ## _finalize(struct cmp_subset *subset)
#define DECLARE_COMPARE(name) \
    static void cmp_subset_ ## name ## _compare(const struct cmp_subset *left, const struct cmp_subset *right, struct diff_tree_node *diff_node)
#define DECLARE_SIM(name) \
    static void cmp_subset_ ## name ## _sim(const struct cmp_subset *left, const struct cmp_subset *right)
#define DECLARE_DESTROY(name) \
    static void cmp_subset_ ## name ## _destroy(struct cmp_subset *subset)

#define REGISTER(name) \
    .data_size = sizeof(struct cmp_subset_ ## name)
#define REGISTER_INIT(name) \
    .init = cmp_subset_ ## name ## _init
#define REGISTER_ADD_NODE(name) \
    .add_node = cmp_subset_ ## name ## _add_node
#define REGISTER_FINALIZE(name) \
    .finalize = cmp_subset_ ## name ## _finalize
#define REGISTER_COMPARE(name) \
    .compare = cmp_subset_ ## name ## _compare
#define REGISTER_SIM(name) \
    .sim = cmp_subset_ ## name ## _sim
#define REGISTER_DESTROY(name) \
    .destroy = cmp_subset_ ## name ## _destroy


DECLARE(container_single) {
    char _;
};
DECLARE_COMPARE(container_single)
{
    assert(!left != !right || (left->items->nel == 1 && right->items->nel == 1));
    cmp_node_compare(left ? left->items->htable[0]->datum : NULL, right ? right->items->htable[0]->datum : NULL, diff_node);
}


DECLARE(container_sim) {
    char _;
};

struct container_sim_compare_args {
    enum diff_side this_side;
    const struct cmp_subset *other_side;
    size_t *unique_len;
    const struct cmp_node ***unique;
};

static int container_sim_compare_map(hashtab_key_t key, hashtab_datum_t datum, void *opaque)
{
    (void)key;
    const struct cmp_node *this_node = datum;
    struct container_sim_compare_args *args = opaque;

    const struct cmp_node *other_node = hashtab_search(MAYBE(args->other_side, items), this_node->full_hash);
    if (!other_node) {
        *args->unique = mem_realloc(*(args->unique), (*args->unique_len + 1) * sizeof(**args->unique));
        (*args->unique)[*args->unique_len] = this_node;
        (*args->unique_len)++;
    }

    return 0;
}

struct sim_array_item {
    struct cmp_sim sim;
    size_t left_i;
    size_t right_i;
};

static int sim_array_item_qsort_cmp(const void *a, const void *b)
{
    const struct sim_array_item *item1 = a;
    const struct sim_array_item *item2 = b;

    return -cmp_sim_cmp(&item1->sim, &item2->sim);
}

DECLARE_COMPARE(container_sim)
{
    size_t unique_left_count = 0;
    const struct cmp_node **unique_left = NULL;
    struct container_sim_compare_args compare_args = {
        .this_side = DIFF_LEFT,
        .other_side = right,
        .unique_len = &unique_left_count,
        .unique = &unique_left,
    };
    hashtab_map(MAYBE(left, items), &container_sim_compare_map, &compare_args);

    size_t unique_right_count = 0;
    const struct cmp_node **unique_right = NULL;
    compare_args = (struct container_sim_compare_args) {
        .this_side = DIFF_RIGHT,
        .other_side = left,
        .unique_len = &unique_right_count,
        .unique = &unique_right,
    };
    hashtab_map(MAYBE(right, items), &container_sim_compare_map, &compare_args);

    if (!unique_left_count || !unique_right_count) {
        for (size_t i = 0; i < unique_left_count; i++) {
            diff_tree_append_diff(diff_node, DIFF_LEFT, unique_left[i]->cil_node, NULL);
        }
        for (size_t i = 0; i < unique_right_count; i++) {
            diff_tree_append_diff(diff_node, DIFF_RIGHT, unique_right[i]->cil_node, NULL);
        }
        return;
    }

    struct sim_array_item *sims = mem_alloc(unique_left_count * unique_right_count * sizeof(*sims));
    for (size_t left_i = 0; left_i < unique_left_count; left_i++) {
        for (size_t right_i = 0; right_i < unique_right_count; right_i++) {
            sims[left_i * unique_right_count + right_i] = (struct sim_array_item) {
                .sim = cmp_node_sim(unique_left[left_i], unique_right[right_i]),
                .left_i = left_i,
                .right_i = right_i,
            };
        }
    }

    qsort(sims, unique_left_count * unique_right_count, sizeof(*sims), &sim_array_item_qsort_cmp);

    for (size_t i = 0; i < unique_left_count * unique_right_count; i++) {
        const struct cmp_node *left_node = unique_left[sims[i].left_i];
        const struct cmp_node *right_node = unique_right[sims[i].right_i];
        if (!left_node || !right_node) {
            continue;
        }
        cmp_node_compare(left_node, right_node, diff_tree_append_child(diff_node, left_node->cil_node, right_node->cil_node));
        unique_left[sims[i].left_i] = NULL;
        unique_right[sims[i].right_i] = NULL;
    }
    for (size_t i = 0; i < unique_left_count; i++) {
        if (!unique_left[i]) {
            continue;
        }
        diff_tree_append_diff(diff_node, DIFF_LEFT, unique_left[i]->cil_node, NULL);
        unique_left[i] = NULL;
    }
    for (size_t i = 0; i < unique_right_count; i++) {
        if (!unique_right[i]) {
            continue;
        }
        diff_tree_append_diff(diff_node, DIFF_RIGHT, unique_right[i]->cil_node, NULL);
        unique_right[i] = NULL;
    }

    mem_free(sims);
    mem_free(unique_left);
    mem_free(unique_right);
}


static const struct cmp_subset_def subset_defs[] = {
    [CIL_ROOT] = {
        REGISTER(container_single),
        REGISTER_COMPARE(container_single),
    },
    [CIL_SRC_INFO] = {
        REGISTER(container_single),
        REGISTER_COMPARE(container_single),
    },
    [CIL_OPTIONAL] = {
        REGISTER(container_sim),
        REGISTER_COMPARE(container_sim),
    }
};
#define SUBSET_DEFS_COUNT (sizeof(subset_defs) / sizeof(*subset_defs))
static const struct cmp_subset_def default_def = { 0 };


const struct cmp_subset_def *cmp_subset_get_def(enum cil_flavor flavor)
{
    if (flavor >= SUBSET_DEFS_COUNT) {
        return &default_def;
    }
    return &subset_defs[flavor];
}
