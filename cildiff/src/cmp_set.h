#ifndef CMP_NODE_SET_H
#define CMP_NODE_SET_H

#include <sepol/policydb/hashtab.h>

#include "cil_node.h"
#include "cmp_common.h"
#include "diff.h"


struct cmp_set {
    char full_hash[HASH_SIZE];
    hashtab_t items; /* key: char partial_hash[HASH_SIZE], value: struct cmp_subset *subset */
};

struct cmp_set *cmp_set_create(struct cil_node *cl_head);

void cmp_set_compare(struct cmp_set *left, struct cmp_set *right, struct diff_tree_node *diff_node);

struct cmp_sim cmp_set_sim(const struct cmp_set *left, struct cmp_set *right);

void cmp_set_destroy(struct cmp_set *set);

#endif
