#ifndef DIFF_H
#define DIFF_H

#include <stdio.h>

#include "cmp_node.h"


enum diff_side {
    DIFF_LEFT,
    DIFF_RIGHT,
    DIFF__MAX
};

struct diff {
    enum diff_side side;
    const struct cmp_node *node;
    char *decription;
    struct diff *next;
};

struct diff_tree_node {
    const struct cmp_node *left_node;
    const struct cmp_node *right_node;

    struct diff_tree_node *parent;
    struct diff_tree_node *cl_head;
    struct diff_tree_node *cl_tail;
    struct diff_tree_node *next;

    struct diff *dl_head;
    struct diff *dl_tail;
};

struct diff_tree_node *diff_tree_create(const struct cmp_node *left_root, const struct cmp_node *right_root);

struct diff_tree_node *diff_tree_append_child(struct diff_tree_node *diff_node_parent, const struct cmp_node *left_node, const struct cmp_node *right_node);

struct diff *diff_tree_append_diff(struct diff_tree_node *diff_node, enum diff_side side, const struct cmp_node *node, char *description);

void diff_tree_print(const struct diff_tree_node *root, FILE *out);

void diff_tree_destroy(struct diff_tree_node *root);

#endif
