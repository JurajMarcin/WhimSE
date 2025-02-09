#include "cil_node.h"

#include <stdlib.h>

#include "mem.h"


struct cil_node *cil_node_from_tree_node(struct cil_tree_node *tree_node)
{
    struct cil_node *cil_node_head = NULL;
    struct cil_node **cil_node = &cil_node_head;
    while (tree_node != NULL) {
        *cil_node = mem_alloc(sizeof(**cil_node));
        **cil_node = (struct cil_node) {
            .flavor = tree_node->flavor,
            .data = tree_node->data,
            .type = CIL_NODE_TREE,
            .orig.tree_node = tree_node,
        };
        cil_node = &(*cil_node)->next;
        tree_node = tree_node->next;
    }
    return cil_node_head;
}

struct cil_node *cil_node_from_list_node(struct cil_list_item *list_item)
{
    struct cil_node *cil_node_head = NULL;
    struct cil_node **cil_node = &cil_node_head;
    while (list_item != NULL) {
        *cil_node = mem_alloc(sizeof(**cil_node));
        **cil_node = (struct cil_node) {
            .flavor = list_item->flavor,
            .data = list_item->data,
            .type = CIL_NODE_LIST,
            .orig.list_item = list_item,
        };
        cil_node = &(*cil_node)->next;
        list_item = list_item->next;
    }
    return cil_node_head;
}

void cil_node_destroy(struct cil_node *cil_node)
{
    while (cil_node) {
        struct cil_node *next = cil_node->next;
        mem_free(cil_node);
        cil_node = next;
    }
}
