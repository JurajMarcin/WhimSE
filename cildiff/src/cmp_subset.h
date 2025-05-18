#ifndef CMP_NODE_SUBSET_H
#define CMP_NODE_SUBSET_H

#include <cil_flavor.h>
#include <sepol/policydb/hashtab.h>

#include "cmp_common.h"
#include "cmp_node.h"
#include "diff.h"

struct cmp_subset {
    enum cil_flavor flavor;
    char full_hash[HASH_SIZE];
    hashtab_t items; /* key: const char full_hash[HASH_SIZE],
                        value: struct cmp_node *node */
    void *data;
};

struct cmp_subset *cmp_subset_create(const struct cmp_node *node);

void cmp_subset_add_node(struct cmp_subset *subset, struct cmp_node *node);

void cmp_subset_finalize(struct cmp_subset *subset);

void cmp_subset_compare(const struct cmp_subset *left,
                        const struct cmp_subset *right,
                        struct diff_tree_node *diff_node);

struct cmp_sim cmp_subset_sim(const struct cmp_subset *left,
                              const struct cmp_subset *right);

void cmp_subset_destroy(struct cmp_subset *subset);

#endif
