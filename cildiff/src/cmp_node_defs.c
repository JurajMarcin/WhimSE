#include "cmp_node_defs.h"

#include <assert.h>
#include <error.h>
#include <string.h>

#include <cil_internal.h>
#include <cil_flavor.h>

#include "cil_node.h"
#include "cil_tree.h"
#include "cmp_common.h"
#include "cmp_node.h"
#include "cmp_set.h"
#include "diff.h"
#include "utils.h"


#define DECLARE(name) \
    static bool cmp_node_init_ ## name (struct cmp_node *node, struct cmp_hash_state *hash_state); \
    static bool __cmp_node_init_ ## name ## _shim (struct cmp_node *node) { \
        struct cmp_hash_state *hash_state = cmp_hash_begin(#name); \
        return cmp_node_init_ ## name (node, hash_state); \
    }
#define DECLARE_WITH_DATA(name) \
    DECLARE(name) \
    static void cmp_node_destroy_ ## name (struct cmp_node *node); \
    struct cmp_node_ ## name
#define DECLARE_COMPARE(name) \
    static void cmp_node_compare_ ## name (const struct cmp_node *left, const struct cmp_node *right, struct diff_tree_node *diff_node)
#define DECLARE_SIM(name) \
    static struct cmp_sim cmp_node_sim_ ## name (const struct cmp_node *left, const struct cmp_node *right)

#define REGISTER(name) \
    .init = &__cmp_node_init_ ## name ## _shim
#define REGISTER_WITH_DATA(name) \
    .init = &__cmp_node_init_ ## name ## _shim, \
    .destroy = &cmp_node_destroy_ ## name, \
    .data_size = sizeof(struct cmp_node_ ## name)
#define REGISTER_COMPARE(name) \
    .compare = &cmp_node_compare_ ## name
#define REGISTER_SIM(name) \
    .sim = &cmp_node_sim_ ## name


DECLARE_WITH_DATA(container) {
    struct cmp_set *items;
};
DECLARE_COMPARE(container);
DECLARE_SIM(container);

DECLARE_WITH_DATA(avrule) {
    struct cmp_set *classperms;
};

DECLARE_WITH_DATA(classperms) {
    struct cmp_set *perms;
};

DECLARE(string)

// DECLARE_WITH_DATA(optional) {
//     struct cmp_set *items;
// };


static const struct cmp_node_def node_defs[] = {
    [CIL_ROOT] = { REGISTER_WITH_DATA(container), REGISTER_COMPARE(container), REGISTER_SIM(container) },
    [CIL_SRC_INFO] = { REGISTER_WITH_DATA(container), REGISTER_COMPARE(container), REGISTER_SIM(container) },
    [CIL_AVRULE] = { REGISTER_WITH_DATA(avrule) },
    [CIL_CLASSPERMS] = { REGISTER_WITH_DATA(classperms) },
    [CIL_STRING] = { REGISTER(string) },
    [CIL_OPTIONAL] = { REGISTER_WITH_DATA(container), REGISTER_COMPARE(container), REGISTER_SIM(container) },
};
#define NODE_DEFS_COUNT (sizeof(node_defs) / sizeof(*node_defs))


const struct cmp_node_def *cmp_node_get_def_flavor(enum cil_flavor flavor)
{
    if (flavor >= NODE_DEFS_COUNT || node_defs[flavor].init == NULL) {
        error(EXIT_FAILURE, 0, "Encountered an unknown node type %d", flavor);
    }
    return &node_defs[flavor];
}

const struct cmp_node_def *cmp_node_get_def(struct cil_node *cil_node)
{
    if (cil_node->flavor >= NODE_DEFS_COUNT || node_defs[cil_node->flavor].init == NULL) {
        struct cil_tree_node tree_node;
        switch (cil_node->type) {
        case CIL_NODE_TREE:
            tree_node = *cil_node->orig.tree_node;
            break;
        case CIL_NODE_LIST:
            tree_node = (struct cil_tree_node) {
                .flavor = cil_node->orig.list_item->flavor,
                .data = cil_node->orig.list_item->data,
            };
            break;
        }
        const char *node_name = cil_node_to_string(&tree_node);
        error(EXIT_FAILURE, 0, "Encountered an unknown node type %d (%s)", cil_node->flavor, node_name);
    }
    return &node_defs[cil_node->flavor];
}


static bool cmp_node_init_container(struct cmp_node *node, struct cmp_hash_state *partial_hash)
{
    assert(node->cil_node->type == CIL_NODE_TREE);
    struct cmp_node_container *data = node->data;
    data->items = cmp_set_create(cil_node_from_tree_node(node->cil_node->orig.tree_node->cl_head));

    cmp_hash_update(partial_hash, sizeof(node->cil_node->flavor), (char *)&node->cil_node->flavor);
    cmp_hash_finish(partial_hash, node->partial_hash);
    memcpy(node->full_hash, data->items->full_hash, HASH_SIZE);
    return true;
}

static void cmp_node_compare_container(const struct cmp_node *left, const struct cmp_node *right, struct diff_tree_node *diff_node)
{
    const struct cmp_node_container *left_data = MAYBE(left, data);
    const struct cmp_node_container *right_data = MAYBE(right, data);
    cmp_set_compare(MAYBE(left_data, items), MAYBE(right_data, items), diff_node);
}

static struct cmp_sim cmp_node_sim_container(const struct cmp_node *left, const struct cmp_node *right)
{
    const struct cmp_node_container *left_data = MAYBE(left, data);
    const struct cmp_node_container *right_data = MAYBE(right, data);
    return cmp_set_sim(MAYBE(left_data, items), MAYBE(right_data, items));
}

static void cmp_node_destroy_container(struct cmp_node *node)
{
    struct cmp_node_container *data = node->data;
    cmp_set_destroy(data->items);
}

static bool cmp_node_init_avrule(struct cmp_node *node, struct cmp_hash_state *partial_hash)
{
    struct cmp_node_avrule *data = node->data;
    struct cil_avrule *avrule = node->cil_node->data;
    data->classperms = cmp_set_create(cil_node_from_list_node(avrule->perms.classperms->head));

    cmp_hash_update(partial_hash, sizeof(avrule->rule_kind), (const char *)&avrule->rule_kind);
    cmp_hash_update_string(partial_hash, avrule->src_str);
    cmp_hash_update_string(partial_hash, avrule->tgt_str);

    struct cmp_hash_state *full_hash = cmp_hash_copy(partial_hash);
    cmp_hash_update(full_hash, HASH_SIZE, data->classperms->full_hash);

    cmp_hash_finish(partial_hash, node->partial_hash);
    cmp_hash_finish(full_hash, node->full_hash);
    return true;
}

static void cmp_node_destroy_avrule(struct cmp_node *node)
{
    struct cmp_node_avrule *data = node->data;
    cmp_set_destroy(data->classperms);
}

static bool cmp_node_init_classperms(struct cmp_node *node, struct cmp_hash_state *full_hash)
{
    struct cmp_node_classperms *data = node->data;
    struct cil_classperms *classperms = node->cil_node->data;
    data->perms = cmp_set_create(cil_node_from_list_node(classperms->perm_strs->head));

    cmp_hash_update_string(full_hash, classperms->class_str);
    cmp_hash_update(full_hash, HASH_SIZE, data->perms->full_hash);

    cmp_hash_finish(full_hash, node->full_hash);
    return false;
}

static void cmp_node_destroy_classperms(struct cmp_node *node)
{
    struct cmp_node_classperms *data = node->data;
    cmp_set_destroy(data->perms);
}

static bool cmp_node_init_string(struct cmp_node *node, struct cmp_hash_state *full_hash)
{
    cmp_hash_update_string(full_hash, node->cil_node->data);

    cmp_hash_finish(full_hash, node->full_hash);
    return false;
}

// static bool cmp_node_init_optional(struct cmp_node *node, struct cmp_hash_state *partial_hash)
// {
//     assert(node->cil_node->type == CIL_NODE_TREE);
//     struct cmp_node_optional *data = node->data;
//     data->items = cmp_set_create(cil_node_from_tree_node(node->cil_node->orig.tree_node->cl_head));

//     struct cmp_hash_state *full_hash = cmp_hash_copy(partial_hash);
//     cmp_hash_update(full_hash, HASH_SIZE, data->items->full_hash);
//
//     cmp_hash_finish(partial_hash, node->partial_hash);
//     cmp_hash_finish(full_hash, node->full_hash);
//     return true;
// }

// static void cmp_node_destroy_optional(struct cmp_node *node)
// {
//     struct cmp_node_optional *data = node->data;
//     cmp_set_destroy(data->items);
// }


const struct cmp_set *cmp_node_src_info_items(const struct cmp_node *node)
{
    assert(node->cil_node->flavor == CIL_SRC_INFO);
    return ((struct cmp_node_container *)node->data)->items;
}
