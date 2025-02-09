#ifndef CIL_NODE_H
#define CIL_NODE_H

#include <cil/cil.h>
#include <cil_flavor.h>
#include <cil_tree.h>


enum cil_node_type {
    CIL_NODE_TREE,
    CIL_NODE_LIST,
};

struct cil_node {
    enum cil_flavor flavor;
    void *data;
    struct cil_node *next;
    enum cil_node_type type;
    union {
        struct cil_tree_node *tree_node;
        struct cil_list_item *list_item;
    } orig;
};

struct cil_node *cil_node_from_tree_node(struct cil_tree_node *tree_node);

struct cil_node *cil_node_from_list_node(struct cil_list_item *list_item);

void cil_node_destroy(struct cil_node *cil_node);

#endif
