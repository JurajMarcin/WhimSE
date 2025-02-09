#ifndef CMP_SUBSET_DEFS_H
#define CMP_SUBSET_DEFS_H

#include "cmp_subset.h"

typedef void (*cmp_subset_init_fn)(struct cmp_subset *subset);
typedef void (*cmp_subset_add_node_fn)(struct cmp_subset *subset, struct cmp_node *node);
typedef bool (*cmp_subset_finalize_fn)(struct cmp_subset *subset);
typedef void (*cmp_subset_compare_fn)(const struct cmp_subset *left, const struct cmp_subset *right, struct diff_tree_node *diff_node);
typedef struct cmp_sim (*cmp_subset_sim_fn)(const struct cmp_subset *left, const struct cmp_subset *right);
typedef void (*cmp_subset_destroy_fn)(struct cmp_subset *subset);

struct cmp_subset_def {
    cmp_subset_init_fn init;
    cmp_subset_add_node_fn add_node;
    cmp_subset_finalize_fn finalize;
    cmp_subset_destroy_fn destroy;
    cmp_subset_compare_fn compare;
    cmp_subset_sim_fn sim;
    size_t data_size;
};

const struct cmp_subset_def *cmp_subset_get_def(enum cil_flavor flavor);

#endif
