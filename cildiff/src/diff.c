#include "diff.h"

#include <stdio.h>
#include <inttypes.h>

#include <cil_write_ast.h>
#include <cil_internal.h>

#include "cil_node.h"
#include "cil_tree.h"
#include "mem.h"


struct diff_tree_node *diff_tree_create(const struct cil_node *left_cil_root, const struct cil_node *right_cil_root)
{
    struct diff_tree_node *diff_node = mem_alloc(sizeof(*diff_node));
    *diff_node = (struct diff_tree_node) {
        .left_cil_node = left_cil_root,
        .right_cil_node = right_cil_root,
    };
    return diff_node;
}

struct diff_tree_node *diff_tree_append_child(struct diff_tree_node *diff_node_parent, const struct cil_node *left_cil_node, const struct cil_node *right_cil_node)
{
    struct diff_tree_node *diff_node = mem_alloc(sizeof(*diff_node));
    *diff_node = (struct diff_tree_node) {
        .left_cil_node = left_cil_node,
        .right_cil_node = right_cil_node,
        .parent = diff_node_parent,
    };
    if (diff_node_parent->cl_tail) {
        diff_node_parent->cl_tail->next = diff_node;
    } else {
        diff_node_parent->cl_head = diff_node;
    }
    diff_node_parent->cl_tail = diff_node;

    return diff_node;
}

struct diff *diff_tree_append_diff(struct diff_tree_node *diff_node, enum diff_side side, const struct cil_node *cil_node, char *description)
{
    struct diff *diff = mem_alloc(sizeof(*diff));
    *diff = (struct diff) {
        .side = side,
        .cil_node = cil_node,
        .decription = description,
    };
    if (diff_node->dl_tail) {
        diff_node->dl_tail->next = diff;
    } else {
        diff_node->dl_head = diff;
    }
    diff_node->dl_tail = diff;

    return diff;
}

static void diff_print_context(enum diff_side side, const struct diff_tree_node *diff_node, FILE *out)
{
    if (diff_node->parent) {
        diff_print_context(side, diff_node->parent, out);
    }
    const struct cil_node *cil_node = side == DIFF_LEFT ? diff_node->left_cil_node : diff_node->right_cil_node;
    switch (cil_node->type) {
    case CIL_NODE_TREE:
        fprintf(out, "; \t%s node on line %" PRIu32 "\n", cil_node_to_string(cil_node->orig.tree_node), cil_node->orig.tree_node->line);
        break;
    case CIL_NODE_LIST:
        fprintf(out, "; \t list item" PRIu32 "\n");
        break;
    }
}

static void diff_print(const struct diff_tree_node *parent, const struct diff *diff, FILE *out)
{
    fprintf(out, "; %s found\n", diff->side == DIFF_LEFT ? "Addition" : "Deletion");
    if (diff->decription) {
        fprintf(out, "; Description: %s\n", diff->decription);
    }
    fprintf(out, "; Left context:\n");
    diff_print_context(DIFF_LEFT, parent, out);
    fprintf(out, "; Right context:\n");
    diff_print_context(DIFF_RIGHT, parent, out);
    fprintf(out, "; %s\n", diff->side == DIFF_LEFT ? "+++": "---");
    cil_write_ast_node(out, diff->cil_node->orig.tree_node);
    cil_write_ast(out, CIL_WRITE_AST_PHASE_BUILD, diff->cil_node->orig.tree_node);
    fprintf(out, "; ===\n");
}

void diff_tree_print(const struct diff_tree_node *root, FILE *out)
{
    for (const struct diff_tree_node *child = root->cl_head; child; child = child->next) {
        diff_tree_print(child, out);
    }
    for (const struct diff *diff = root->dl_head; diff; diff = diff->next) {
        diff_print(root, diff, out);
    }
}

void diff_tree_destroy(struct diff_tree_node *root)
{
    struct diff_tree_node *child = root->cl_head;
    while (child) {
        struct diff_tree_node *next = child->next;
        diff_tree_destroy(child);
        child = next;
    }
    struct diff *diff = root->dl_head;
    while (diff) {
        struct diff *next = diff->next;
        mem_free(diff->decription);
        mem_free(diff);
        diff = next;
    }
    mem_free(root);
}
