#include "diff.h"

#include <assert.h>
#include <stdio.h>
#include <inttypes.h>

#include <cil/cil.h>
#include <cil_internal.h>
#include <cil_tree.h>
#include <cil_write_ast.h>

#include "mem.h"


struct diff_tree_node *diff_tree_create(const struct cmp_node *left_root, const struct cmp_node *right_root)
{
    struct diff_tree_node *diff_node = mem_alloc(sizeof(*diff_node));
    *diff_node = (struct diff_tree_node) {
        .left_node = left_root,
        .right_node = right_root,
    };
    return diff_node;
}

struct diff_tree_node *diff_tree_append_child(struct diff_tree_node *diff_node_parent, const struct cmp_node *left_node, const struct cmp_node *right_node)
{
    struct diff_tree_node *diff_node = mem_alloc(sizeof(*diff_node));
    *diff_node = (struct diff_tree_node) {
        .left_node = left_node,
        .right_node = right_node,
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

struct diff *diff_tree_append_diff(struct diff_tree_node *diff_node, enum diff_side side, const struct cmp_node *node, char *description)
{
    struct diff *diff = mem_alloc(sizeof(*diff));
    *diff = (struct diff) {
        .side = side,
        .node = node,
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
    const struct cmp_node *node = side == DIFF_LEFT ? diff_node->left_node : diff_node->right_node;
    assert(node);
    fprintf(out, "; \t%s node on line %" PRIu32 "\n", cil_node_to_string(node->cil_node), node->cil_node->line);
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
    cil_write_ast_node(out, diff->node->cil_node);
    switch (diff->node->cil_node->flavor) {
    case CIL_CLASS:
    case CIL_COMMON:
    case CIL_MAP_CLASS:
        break;
    default:
        cil_write_ast(out, CIL_WRITE_AST_PHASE_BUILD, diff->node->cil_node);
        break;
    }
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
