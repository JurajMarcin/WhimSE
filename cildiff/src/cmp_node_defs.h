#ifndef CMP_NODE_DEFS_H
#define CMP_NODE_DEFS_H

#include <stdbool.h>

#include "cmp_node.h"
#include "diff.h"


typedef bool (*cmp_node_init_fn)(struct cmp_node *node);
typedef void (*cmp_node_compare_fn)(const struct cmp_node *left, const struct cmp_node *right, struct diff_tree_node *diff_node);
typedef struct cmp_sim (*cmp_node_sim_fn)(const struct cmp_node *left, const struct cmp_node *right);
typedef void (*cmp_node_destroy_fn)(struct cmp_node *node);

struct cmp_node_def {
    cmp_node_init_fn init;
    cmp_node_compare_fn compare;
    cmp_node_sim_fn sim;
    cmp_node_destroy_fn destroy;
    size_t data_size;
};

const struct cmp_node_def *cmp_node_get_def(const struct cil_tree_node *cil_node);

const struct cmp_set *cmp_node_src_info_items(const struct cmp_node *node);

#endif
