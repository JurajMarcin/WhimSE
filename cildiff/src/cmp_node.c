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

#include "cmp_node.h"

#include <assert.h>
#include <string.h>

#include <cil/cil.h>
#include <cil_tree.h>

#include "cmp_common.h"
#include "cmp_node_defs.h"
#include "mem.h"
#include "utils.h"

struct cmp_node *cmp_node_create(struct cil_tree_node *cil_node)
{
    const struct cmp_node_def *def = cmp_node_get_def(cil_node);
    struct cmp_node *node = mem_alloc(sizeof(*node));
    *node = (struct cmp_node) {
        .cil_node = cil_node,
    };
    if (def->data_size) {
        node->data = mem_alloc(def->data_size);
        memset(node->data, 0, def->data_size);
    }
    if (!def->init(node)) {
        memcpy(node->partial_hash, node->full_hash, HASH_SIZE);
    }
    return node;
}

void cmp_node_compare(const struct cmp_node *left, const struct cmp_node *right,
                      struct diff_tree_node *diff_node)
{
    assert(!left != !right
           || left->cil_node->flavor == right->cil_node->flavor);
    const struct cmp_node_def *def =
        cmp_node_get_def(EITHER(left, right, cil_node));
    if (def->compare) {
        def->compare(left, right, diff_node);
    }
}

struct cmp_sim cmp_node_sim(const struct cmp_node *left,
                            const struct cmp_node *right)
{
    if (!left && !right) {
        return (struct cmp_sim) { 0 };
    }
    assert(!left || !right
           || left->cil_node->flavor == right->cil_node->flavor);
    const struct cmp_node_def *def =
        cmp_node_get_def(EITHER(left, right, cil_node));
    if (def->sim) {
        return def->sim(left, right);
    }
    if (cmp_hash_cmp(left->full_hash, right->full_hash)) {
        return (struct cmp_sim) { .left = !right, .right = !left };
    }
    return (struct cmp_sim) { .common = 1 };
}

void cmp_node_destroy(struct cmp_node *node)
{
    if (!node) {
        return;
    }
    const struct cmp_node_def *def = cmp_node_get_def(node->cil_node);
    if (def->destroy) {
        def->destroy(node);
    }
    mem_free(node->data);
    mem_free(node);
}
