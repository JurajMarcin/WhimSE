#ifndef CMP_NODE_H
#define CMP_NODE_H

#include <sepol/policydb/hashtab.h>

#include "cmp_common.h"
#include "diff.h"


struct cmp_node {
    struct cil_tree_node *cil_node;
    char partial_hash[HASH_SIZE];
    char full_hash[HASH_SIZE];
    void *data;
};

struct cmp_node *cmp_node_create(struct cil_tree_node *cil_node);

void cmp_node_compare(const struct cmp_node *left, const struct cmp_node *right, struct diff_tree_node *diff_node);

struct cmp_sim cmp_node_sim(const struct cmp_node *left, const struct cmp_node *right);

void cmp_node_destroy(struct cmp_node *node);

#endif
