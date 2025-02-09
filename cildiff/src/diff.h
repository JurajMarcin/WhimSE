#ifndef DIFF_H
#define DIFF_H

#include <stdio.h>

#include <cil/cil.h>
#include <cil_tree.h>

#include "cil_node.h"


enum diff_side {
    DIFF_LEFT,
    DIFF_RIGHT,
};

struct diff {
    enum diff_side side;
    const struct cil_node *cil_node;
    char *decription;
    struct diff *next;
};

struct diff_tree_node {
    const struct cil_node *left_cil_node;
    const struct cil_node *right_cil_node;

    struct diff_tree_node *parent;
    struct diff_tree_node *cl_head;
    struct diff_tree_node *cl_tail;
    struct diff_tree_node *next;

    struct diff *dl_head;
    struct diff *dl_tail;
};

struct diff_tree_node *diff_tree_create(const struct cil_node *left_cil_root, const struct cil_node *right_cil_root);

struct diff_tree_node *diff_tree_append_child(struct diff_tree_node *diff_node_parent, const struct cil_node *left_cil_node, const struct cil_node *right_cil_node);

struct diff *diff_tree_append_diff(struct diff_tree_node *diff_node, enum diff_side side, const struct cil_node *cil_node, char *description);

void diff_tree_print(const struct diff_tree_node *root, FILE *out);

void diff_tree_destroy(struct diff_tree_node *root);

#endif
