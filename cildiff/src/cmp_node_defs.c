/*
 * Copyright (C) 2025 Juraj Marcin <juraj@jurajmarcin.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

#include "cmp_node_defs.h"

#include <assert.h>
#include <error.h>
#include <string.h>

#include <cil_internal.h>
#include <cil_flavor.h>
#include <cil_tree.h>

#include "cmp_common.h"
#include "cmp_data.h"
#include "cmp_node.h"
#include "cmp_set.h"
#include "diff.h"
#include "utils.h"


#define DECLARE_NODE(name) \
struct cmp_node_ ## name
#define DECLARE_NODE_INIT(name) \
static bool cmp_node_init_ ## name (struct cmp_node *node)
#define DECLARE_NODE_COMPARE(name) \
static void cmp_node_compare_ ## name (const struct cmp_node *left, const struct cmp_node *right, struct diff_tree_node *diff_node)
#define DECLARE_NODE_SIM(name) \
static struct cmp_sim cmp_node_sim_ ## name (const struct cmp_node *left, const struct cmp_node *right)
#define DECLARE_NODE_DESTROY(name) \
static void cmp_node_destroy_ ## name (struct cmp_node *node)

#define REGISTER_NODE(name) \
    .init = &cmp_node_init_ ## name, \
    .destroy = &cmp_node_destroy_ ## name, \
    .data_size = sizeof(struct cmp_node_ ## name)
#define REGISTER_NODE_COMPARE(name) \
    .compare = &cmp_node_compare_ ## name
#define REGISTER_NODE_SIM(name) \
    .sim = &cmp_node_sim_ ## name


/******************************************************************************
 *   Common Nodes                                                             *
 ******************************************************************************/

DECLARE_NODE(container) {
    struct cmp_set *items;
};
DECLARE_NODE_INIT(container)
{
    struct cmp_node_container *data = node->data;
    data->items = cmp_set_create(node->cil_node->cl_head);

    struct cmp_data cmp_data = {0};
    cmp_data_init(node->cil_node->flavor, node->cil_node->data, &cmp_data);

    memcpy(node->partial_hash, cmp_data.partial_hash, HASH_SIZE);

    struct cmp_hash_state *hash_state = cmp_hash_begin(NULL);
    cmp_hash_update(hash_state, HASH_SIZE, cmp_data.full_hash);
    cmp_hash_update(hash_state, HASH_SIZE, data->items->full_hash);
    cmp_hash_finish(hash_state, node->full_hash);

    return true;
}
DECLARE_NODE_COMPARE(container)
{
    const struct cmp_node_container *left_data = MAYBE(left, data);
    const struct cmp_node_container *right_data = MAYBE(right, data);
    cmp_set_compare(MAYBE(left_data, items), MAYBE(right_data, items), diff_node);
}
DECLARE_NODE_SIM(container)
{
    const struct cmp_node_container *left_data = MAYBE(left, data);
    const struct cmp_node_container *right_data = MAYBE(right, data);
    return cmp_set_sim(MAYBE(left_data, items), MAYBE(right_data, items));
}
DECLARE_NODE_DESTROY(container)
{
    struct cmp_node_container *data = node->data;
    cmp_set_destroy(data->items);
}

/******************************************************************************
 *  Conditional Statements                                                    *
 ******************************************************************************/

enum {
    COND_ITEMS_FALSE = 0,
    COND_ITEMS_TRUE,
    COND_ITEMS__MAX,
};

DECLARE_NODE(cond_container) {
    struct cmp_set *items[2];
};
DECLARE_NODE_INIT(cond_container)
{
    struct cmp_node_cond_container *data = node->data;
    struct cmp_data cmp_data = {0};
    cmp_data_init(node->cil_node->flavor, node->cil_node->data, &cmp_data);
    memcpy(node->partial_hash, cmp_data.partial_hash, HASH_SIZE);

    for (const struct cil_tree_node *condblock = node->cil_node->cl_head; condblock; condblock = condblock->next) {
        assert(condblock->flavor == CIL_CONDBLOCK);
        static const int cil_cond_map[] = {
            [CIL_CONDFALSE] = COND_ITEMS_FALSE,
            [CIL_CONDTRUE] = COND_ITEMS_TRUE,
        };
        const struct cil_condblock *condblock_data = condblock->data;
        data->items[cil_cond_map[condblock_data->flavor]] = cmp_set_create(condblock->cl_head);
    }

    struct cmp_hash_state *hash_state = cmp_hash_begin(NULL);
    cmp_hash_update(hash_state, HASH_SIZE, cmp_data.full_hash);

    for (size_t i = 0; i < COND_ITEMS__MAX; i++) {
        static const char *cond_name_map[] = {
            [COND_ITEMS_FALSE] = "<cond::false>",
            [COND_ITEMS_TRUE] = "<cond::true>",
        };
        cmp_hash_update_string(hash_state, cond_name_map[i]);
        if (data->items[i]) {
            cmp_hash_update(hash_state, HASH_SIZE, data->items[i]->full_hash);
        } else {
            cmp_hash_update_string(hash_state, "<cond::empty>");
        }
    }
    cmp_hash_finish(hash_state, node->full_hash);

    return true;
}
DECLARE_NODE_COMPARE(cond_container)
{
    const struct cmp_node_cond_container *left_data = MAYBE(left, data);
    const struct cmp_node_cond_container *right_data = MAYBE(right, data);
    for (size_t i = 0; i < COND_ITEMS__MAX; i++) {
        cmp_set_compare(MAYBE(left_data, items[i]), MAYBE(right_data, items[i]), diff_node);
    }
}
DECLARE_NODE_SIM(cond_container)
{
    const struct cmp_node_cond_container *left_data = MAYBE(left, data);
    const struct cmp_node_cond_container *right_data = MAYBE(right, data);
    struct cmp_sim total_sim = {0};
    for (size_t i = 0; i < COND_ITEMS__MAX; i++) {
        struct cmp_sim sim = cmp_set_sim(MAYBE(left_data, items[i]), MAYBE(right_data, items[i]));
        cmp_sim_add(&total_sim, &sim);
    }
    return total_sim;
}
DECLARE_NODE_DESTROY(cond_container)
{
    struct cmp_node_cond_container *data = node->data;
    for (size_t i = 0; i < COND_ITEMS__MAX; i++) {
        cmp_set_destroy(data->items[i]);
    }
}


static const struct cmp_node_def node_defs[] = {
    /* Common and Utility Nodes */
    [CIL_ROOT] = { REGISTER_NODE(container), REGISTER_NODE_COMPARE(container), REGISTER_NODE_SIM(container) },
    [CIL_SRC_INFO] = { REGISTER_NODE(container), REGISTER_NODE_COMPARE(container), REGISTER_NODE_SIM(container) },
    /* Call / Macro Statements */
    [CIL_MACRO] = { REGISTER_NODE(container), REGISTER_NODE_COMPARE(container) },
    /* Class and Permission Statements */
    [CIL_COMMON] = { REGISTER_NODE(container), REGISTER_NODE_COMPARE(container) },
    [CIL_CLASS] = { REGISTER_NODE(container), REGISTER_NODE_COMPARE(container) },
    [CIL_MAP_CLASS] = { REGISTER_NODE(container), REGISTER_NODE_COMPARE(container) },
    /* Conditional Statements */
    [CIL_BOOLEANIF] = { REGISTER_NODE(cond_container), REGISTER_NODE_COMPARE(cond_container), REGISTER_NODE_SIM(cond_container) },
    [CIL_TUNABLEIF] = { REGISTER_NODE(cond_container), REGISTER_NODE_COMPARE(cond_container), REGISTER_NODE_SIM(cond_container) },
    /* Container Statements */
    [CIL_BLOCK] = { REGISTER_NODE(container), REGISTER_NODE_COMPARE(container) },
    [CIL_OPTIONAL] = { REGISTER_NODE(container), REGISTER_NODE_COMPARE(container), REGISTER_NODE_SIM(container) },
    [CIL_IN] = { REGISTER_NODE(container), REGISTER_NODE_COMPARE(container) },
};
#define NODE_DEFS_COUNT (sizeof(node_defs) / sizeof(*node_defs))


static bool cmp_node_default_init(struct cmp_node *node)
{
    struct cmp_data cmp_data = {0};
    cmp_data_init(node->cil_node->flavor, node->cil_node->data, &cmp_data);
    memcpy(node->partial_hash, cmp_data.partial_hash, HASH_SIZE);
    memcpy(node->full_hash, cmp_data.full_hash, HASH_SIZE);
    return false;
}


static const struct cmp_node_def default_def = { .init = &cmp_node_default_init };


const struct cmp_node_def *cmp_node_get_def_flavor(enum cil_flavor flavor)
{
    if (flavor >= NODE_DEFS_COUNT || node_defs[flavor].init == NULL) {
        return &default_def;
    }
    return &node_defs[flavor];
}

const struct cmp_node_def *cmp_node_get_def(const struct cil_tree_node *cil_node)
{
    if (cil_node->flavor >= NODE_DEFS_COUNT || node_defs[cil_node->flavor].init == NULL) {
        return &default_def;
    }
    return &node_defs[cil_node->flavor];
}

const struct cmp_set *cmp_node_src_info_items(const struct cmp_node *node)
{
    assert(node->cil_node->flavor == CIL_SRC_INFO);
    return ((struct cmp_node_container *)node->data)->items;
}
