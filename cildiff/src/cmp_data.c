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

#include "cmp_data.h"

#include <assert.h>
#include <error.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include <cil_flavor.h>
#include <cil_internal.h>
#include <cil_list.h>

#include "cmp_common.h"
#include "mem.h"
#include "utils.h"

typedef void (*cmp_data_init_fn)(const void *cil_data,
                                 struct cmp_hash_state *full_hash,
                                 struct cmp_hash_state **partial_hash);

struct cmp_data_def {
    const char *flavor_name;
    cmp_data_init_fn init;
};

#define DEFINE_DATA(name, type)                                                \
    static void cmp_data_##name##_init(const type *name,                       \
                                       struct cmp_hash_state *full_hash,       \
                                       struct cmp_hash_state **partial_hash);  \
    static void __cmp_data_##name##_init_shim(                                 \
        const void *cil_data, struct cmp_hash_state *full_hash,                \
        struct cmp_hash_state **partial_hash)                                  \
    {                                                                          \
        cmp_data_##name##_init(cil_data, full_hash, partial_hash);             \
    }                                                                          \
    static void cmp_data_##name##_init(const type *name,                       \
                                       struct cmp_hash_state *full_hash,       \
                                       struct cmp_hash_state **partial_hash)

#define REGISTER_DATA(name)                                                    \
    .flavor_name = #name, .init = __cmp_data_##name##_init_shim

/******************************************************************************
 *  Common                                                                    *
 ******************************************************************************/

#define DEFINE_DATA_SIMPLE_DECL(decl_name, type)                               \
    DEFINE_DATA(decl_name, struct cil_symtab_datum)                            \
    {                                                                          \
        UNUSED(partial_hash);                                                  \
        static_assert(offsetof(type, datum) == 0,                              \
                      #decl_name " is not a simple CIL declaration");          \
        cmp_hash_update_string(full_hash, decl_name->name);                    \
    }

#define DEFINE_DATA_ALIAS(decl_name)                                           \
    DEFINE_DATA_SIMPLE_DECL(decl_name, struct cil_alias)

#define DEFINE_DATA_ALIAS_ACTUAL(decl_name)                                    \
    DEFINE_DATA(decl_name, struct cil_aliasactual)                             \
    {                                                                          \
        cmp_hash_update_string(full_hash, decl_name->alias_str);               \
        *partial_hash = cmp_hash_copy(full_hash);                              \
        cmp_hash_update_string(full_hash, decl_name->actual_str);              \
    }

void hash_str_or_data(struct cmp_hash_state *hash_state, enum cil_flavor flavor,
                      const char *str, const void *data)
{
    if (str) {
        cmp_hash_update_string(hash_state, str);
    } else {
        struct cmp_data cmp_data = { 0 };
        cmp_data_init(flavor, data, &cmp_data);
        cmp_hash_update(hash_state, HASH_SIZE, cmp_data.full_hash);
    }
}

static void hash_cil_expr(const struct cil_list *expr,
                          char full_hash[HASH_SIZE])
{
    struct cmp_hash_state *hash_state = cmp_hash_begin("<expr>");
    cmp_hash_update(hash_state, sizeof(expr->flavor), &expr->flavor);

    size_t expr_len = 0;
    for (const struct cil_list_item *expr_item = expr->head; expr_item;
         expr_item = expr_item->next) {
        expr_len++;
    }
    if (!expr_len) {
        goto exit;
    }

    const struct cil_list_item *expr_item = expr->head;
    if (expr_item->flavor == CIL_OP) {
        cmp_hash_update_string(hash_state, "<expr_op>");
        cmp_hash_update(hash_state, sizeof(expr_item->data), &expr_item->data);
        expr_item = expr_item->next;
        expr_len--;
    }

    char *children_hashes = mem_alloc(HASH_SIZE * expr_len);
    memset(children_hashes, 0, HASH_SIZE * expr_len);
    for (size_t i = 0; i < expr_len; expr_item = expr_item->next, i++) {
        switch (expr_item->flavor) {
        case CIL_STRING:
            cmp_hash(strlen(expr_item->data) + 1, expr_item->data,
                     children_hashes + i * HASH_SIZE);
            break;
        case CIL_LIST:
            hash_cil_expr(expr_item->data, children_hashes + i * HASH_SIZE);
            break;
        case CIL_CONS_OPERAND:
            cmp_hash(sizeof(expr_item->data), &expr_item->data,
                     children_hashes + i * HASH_SIZE);
            break;
        default:
            error(EXIT_FAILURE, 0,
                  "hash_cil_expr: Invalid node in expr list %d",
                  expr_item->flavor);
        }
    }
    assert(!expr_item);

    qsort(children_hashes, expr_len, HASH_SIZE, &cmp_hash_qsort_cmp);
    cmp_hash_update(hash_state, expr_len * HASH_SIZE, children_hashes);
    mem_free(children_hashes);

exit:
    cmp_hash_finish(hash_state, full_hash);
}

enum list_order {
    LIST_ORDER_UNORDERED,
    LIST_ORDER_ALLOW_UNORDERED,
    LIST_ORDER_ORDERED,
};

static void hash_cil_string_list(const struct cil_list *list,
                                 enum list_order order,
                                 char full_hash[HASH_SIZE])
{
    struct cmp_hash_state *hash_state = cmp_hash_begin("<list>");
    cmp_hash_update(hash_state, sizeof(list->flavor), &list->flavor);

    size_t list_len = 0;
    for (const struct cil_list_item *list_item = list->head; list_item;
         list_item = list_item->next) {
        list_len++;
        if (list_item->flavor != CIL_STRING) {
            error(EXIT_FAILURE, 0,
                  "hash_cil_expr: Invalid node in string list %d",
                  list_item->flavor);
        }
    }
    if (!list_len) {
        goto exit;
    }

    const struct cil_list_item *list_item = list->head;
    if (list_item->data == CIL_KEY_UNORDERED) {
        if (order != LIST_ORDER_ALLOW_UNORDERED) {
            error(
                EXIT_FAILURE, 0,
                "hash_cil_expr: List cannot be marked with 'unordered' keyword");
        }
        order = LIST_ORDER_UNORDERED;
        list_item = list_item->next;
        list_len--;
    }
    switch (order) {
    case LIST_ORDER_UNORDERED:
        cmp_hash_update_string(hash_state, "<unordered>");
        break;
    case LIST_ORDER_ALLOW_UNORDERED:
    case LIST_ORDER_ORDERED:
        cmp_hash_update_string(hash_state, "<ordered>");
        break;
    }
    char *children_hashes = mem_alloc(HASH_SIZE * list_len);
    memset(children_hashes, 0, HASH_SIZE * list_len);
    for (size_t i = 0; i < list_len; list_item = list_item->next, i++) {
        cmp_hash(strlen(list_item->data) + 1, list_item->data,
                 children_hashes + i * HASH_SIZE);
    }
    assert(!list_item);

    if (order == LIST_ORDER_UNORDERED) {
        qsort(children_hashes, list_len, HASH_SIZE, &cmp_hash_qsort_cmp);
    }
    cmp_hash_update(hash_state, list_len * HASH_SIZE, children_hashes);
    mem_free(children_hashes);

exit:
    cmp_hash_finish(hash_state, full_hash);
}

#define DEFINE_DATA_BOUNDS(decl_name)                                          \
    DEFINE_DATA(decl_name, struct cil_bounds)                                  \
    {                                                                          \
        UNUSED(partial_hash);                                                  \
        cmp_hash_update_string(full_hash, decl_name->parent_str);              \
        cmp_hash_update_string(full_hash, decl_name->child_str);               \
    }

#define DEFINE_DATA_ATTRIBUTESET(decl_name, type)                              \
    DEFINE_DATA(decl_name, type)                                               \
    {                                                                          \
        cmp_hash_update_string(full_hash, decl_name->attr_str);                \
        *partial_hash = cmp_hash_copy(full_hash);                              \
        char expr_hash[HASH_SIZE];                                             \
        hash_cil_expr(decl_name->str_expr, expr_hash);                         \
        cmp_hash_update(full_hash, HASH_SIZE, expr_hash);                      \
    }

#define DEFINE_DATA_ORDERED(decl_name, order)                                  \
    DEFINE_DATA(decl_name, struct cil_ordered)                                 \
    {                                                                          \
        *partial_hash = cmp_hash_copy(full_hash);                              \
        char order_hash[HASH_SIZE];                                            \
        hash_cil_string_list(decl_name->strs, order, order_hash);              \
        cmp_hash_update(full_hash, HASH_SIZE, order_hash);                     \
    }

void hash_call_args_tree(const struct cil_tree_node *cil_node,
                         char full_hash[HASH_SIZE])
{
    assert(!cil_node->cl_head || !cil_node->data);
    struct cmp_hash_state *hash_state =
        cmp_hash_begin(cil_node->data ? "<string>" : "<list>");
    if (cil_node->data) {
        cmp_hash_update_string(hash_state, cil_node->data);
    }
    for (const struct cil_tree_node *child = cil_node->cl_head; child;
         child = child->next) {
        char child_full_hash[HASH_SIZE] = { 0 };
        hash_call_args_tree(child, child_full_hash);
        cmp_hash_update(hash_state, HASH_SIZE, child_full_hash);
    }
    cmp_hash_finish(hash_state, full_hash);
}

/******************************************************************************
 *  Basic                                                                     *
 ******************************************************************************/

DEFINE_DATA(string, char)
{
    UNUSED(partial_hash);
    cmp_hash_update_string(full_hash, string);
}

DEFINE_DATA(root, struct cil_root)
{
    UNUSED(root);
    UNUSED(full_hash);
    UNUSED(partial_hash);
}

DEFINE_DATA(src_info, struct cil_src_info)
{
    UNUSED(src_info);
    UNUSED(full_hash);
    UNUSED(partial_hash);
}

/******************************************************************************
 *  Access Vector Rules                                                       *
 ******************************************************************************/

DEFINE_DATA(avrule, struct cil_avrule)
{
    cmp_hash_update(full_hash, sizeof(avrule->is_extended),
                    &avrule->is_extended);
    cmp_hash_update(full_hash, sizeof(avrule->rule_kind), &avrule->rule_kind);
    cmp_hash_update_string(full_hash, avrule->src_str);
    cmp_hash_update_string(full_hash, avrule->tgt_str);
    *partial_hash = cmp_hash_copy(full_hash);
    if (avrule->is_extended) {
        hash_str_or_data(full_hash, CIL_PERMISSIONX, avrule->perms.x.permx_str,
                         avrule->perms.x.permx);
    } else {
        /*
         * After building AST, avrule should have a single anonymous or named
         * classpermissionset
         */
        assert(avrule->perms.classperms->head
               == avrule->perms.classperms->tail);
        struct cmp_data perms = { 0 };
        cmp_data_init(avrule->perms.classperms->head->flavor,
                      avrule->perms.classperms->head->data, &perms);
        cmp_hash_update(full_hash, HASH_SIZE, perms.full_hash);
    }
}

DEFINE_DATA(deny, struct cil_deny_rule)
{
    cmp_hash_update_string(full_hash, deny->src_str);
    cmp_hash_update_string(full_hash, deny->tgt_str);
    *partial_hash = cmp_hash_copy(full_hash);
    /*
     * After building AST, deny should have a single anonymous or named
     * classpermissionset
     */
    assert(deny->classperms->head == deny->classperms->tail);
    struct cmp_data perms = { 0 };
    cmp_data_init(deny->classperms->head->flavor, deny->classperms->head->data,
                  &perms);
    cmp_hash_update(full_hash, HASH_SIZE, perms.full_hash);
}

/******************************************************************************
 *  Call / Macro Statements                                                   *
 ******************************************************************************/

DEFINE_DATA(call, struct cil_call)
{
    UNUSED(partial_hash);
    cmp_hash_update_string(full_hash, call->macro_str);
    char args_hash[HASH_SIZE] = { 0 };
    hash_call_args_tree(call->args_tree->root, args_hash);
    cmp_hash_update(full_hash, HASH_SIZE, args_hash);
}

DEFINE_DATA(macro, struct cil_macro)
{
    cmp_hash_update_string(full_hash, macro->datum.name);
    *partial_hash = cmp_hash_copy(full_hash);

    for (const struct cil_list_item *item = macro->params->head; item;
         item = item->next) {
        assert(item->flavor == CIL_PARAM);
        const struct cil_param *param = item->data;
        cmp_hash_update(full_hash, sizeof(param->flavor), &param->flavor);
        cmp_hash_update_string(full_hash, param->str);
    }
}

/******************************************************************************
 *  Class and Permission Statements                                           *
 ******************************************************************************/

DEFINE_DATA_SIMPLE_DECL(perm, struct cil_perm)
DEFINE_DATA_SIMPLE_DECL(common, struct cil_class)

DEFINE_DATA(classcommon, struct cil_classcommon)
{
    cmp_hash_update_string(full_hash, classcommon->class_str);
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update_string(full_hash, classcommon->common_str);
}
DEFINE_DATA_SIMPLE_DECL(class, struct cil_class)
DEFINE_DATA_ORDERED(classorder, LIST_ORDER_ALLOW_UNORDERED)
DEFINE_DATA_SIMPLE_DECL(classpermission, struct cil_classpermission)

DEFINE_DATA(classperms_set, struct cil_classperms_set)
{
    UNUSED(partial_hash);
    cmp_hash_update_string(full_hash, classperms_set->set_str);
}

DEFINE_DATA(classperms, struct cil_classperms)
{
    cmp_hash_update_string(full_hash, classperms->class_str);
    *partial_hash = cmp_hash_copy(full_hash);
    char perms_hash[HASH_SIZE] = { 0 };
    hash_cil_expr(classperms->perm_strs, perms_hash);
    cmp_hash_update(full_hash, HASH_SIZE, perms_hash);
}

DEFINE_DATA(classpermissionset, struct cil_classpermissionset)
{
    cmp_hash_update_string(full_hash, classpermissionset->set_str);
    *partial_hash = cmp_hash_copy(full_hash);
    assert(classpermissionset->classperms->head
           == classpermissionset->classperms->tail);
    assert(classpermissionset->classperms->head->flavor == CIL_CLASSPERMS);
    struct cmp_data perms = { 0 };
    cmp_data_init(CIL_CLASSPERMS, classpermissionset->classperms->head->data,
                  &perms);
    cmp_hash_update(full_hash, HASH_SIZE, perms.full_hash);
}
DEFINE_DATA_SIMPLE_DECL(classmap, struct cil_class)

DEFINE_DATA(classmapping, struct cil_classmapping)
{
    cmp_hash_update_string(full_hash, classmapping->map_class_str);
    cmp_hash_update_string(full_hash, classmapping->map_perm_str);
    *partial_hash = cmp_hash_copy(full_hash);
    /*
     * After building AST, classmapping should have a single anonymous or named
     * classpermissionset
     */
    assert(classmapping->classperms->head == classmapping->classperms->tail);
    struct cmp_data perms = { 0 };
    cmp_data_init(classmapping->classperms->head->flavor,
                  classmapping->classperms->head->data, &perms);
    cmp_hash_update(full_hash, HASH_SIZE, perms.full_hash);
}

DEFINE_DATA(permissionx, struct cil_permissionx)
{
    if (permissionx->datum.name) {
        cmp_hash_update_string(full_hash, permissionx->datum.name);
    } else {
        cmp_hash_update_string(full_hash, "<anonymous::permissionx>");
    }
    cmp_hash_update(full_hash, sizeof(permissionx->kind), &permissionx->kind);
    cmp_hash_update_string(full_hash, permissionx->obj_str);
    *partial_hash = cmp_hash_copy(full_hash);
    char perms_hash[HASH_SIZE];
    hash_cil_expr(permissionx->expr_str, perms_hash);
    cmp_hash_update(full_hash, HASH_SIZE, perms_hash);
}

/******************************************************************************
 *  Conditional Statements                                                    *
 ******************************************************************************/

DEFINE_DATA(boolean, struct cil_bool)
{
    cmp_hash_update_string(full_hash, boolean->datum.name);
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update(full_hash, sizeof(boolean->value), &boolean->value);
}

DEFINE_DATA(booleanif, struct cil_booleanif)
{
    char expr_hash[HASH_SIZE];
    hash_cil_expr(booleanif->str_expr, expr_hash);
    cmp_hash_update(full_hash, HASH_SIZE, expr_hash);
    *partial_hash = cmp_hash_copy(full_hash);
}

DEFINE_DATA(tunable, struct cil_tunable)
{
    cmp_hash_update_string(full_hash, tunable->datum.name);
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update(full_hash, sizeof(tunable->value), &tunable->value);
}

DEFINE_DATA(tunableif, struct cil_tunableif)
{
    char expr_hash[HASH_SIZE];
    hash_cil_expr(tunableif->str_expr, expr_hash);
    cmp_hash_update(full_hash, HASH_SIZE, expr_hash);
    *partial_hash = cmp_hash_copy(full_hash);
}

/******************************************************************************
 *  Constaint Statements                                                      *
 ******************************************************************************/

DEFINE_DATA(constrain, struct cil_constrain)
{
    /*
     * After building AST, constrain should have a single anonymous or named
     * classpermissionset
     */
    assert(constrain->classperms->head == constrain->classperms->tail);
    struct cmp_data perms = { 0 };
    cmp_data_init(constrain->classperms->head->flavor,
                  constrain->classperms->head->data, &perms);
    cmp_hash_update(full_hash, HASH_SIZE, perms.full_hash);
    *partial_hash = cmp_hash_copy(full_hash);
    char expr_hash[HASH_SIZE];
    hash_cil_expr(constrain->str_expr, expr_hash);
    cmp_hash_update(full_hash, HASH_SIZE, expr_hash);
}

DEFINE_DATA(validatetrans, struct cil_validatetrans)
{
    cmp_hash_update_string(full_hash, validatetrans->class_str);
    *partial_hash = cmp_hash_copy(full_hash);
    char expr_hash[HASH_SIZE];
    hash_cil_expr(validatetrans->str_expr, expr_hash);
    cmp_hash_update(full_hash, HASH_SIZE, expr_hash);
}

DEFINE_DATA(mlsconstrain, struct cil_constrain)
{
    /*
     * After building AST, mlsconstrain should have a single anonymous or named
     * classpermissionset
     */
    assert(mlsconstrain->classperms->head == mlsconstrain->classperms->tail);
    struct cmp_data perms = { 0 };
    cmp_data_init(mlsconstrain->classperms->head->flavor,
                  mlsconstrain->classperms->head->data, &perms);
    cmp_hash_update(full_hash, HASH_SIZE, perms.full_hash);
    *partial_hash = cmp_hash_copy(full_hash);
    char expr_hash[HASH_SIZE];
    hash_cil_expr(mlsconstrain->str_expr, expr_hash);
    cmp_hash_update(full_hash, HASH_SIZE, expr_hash);
}

DEFINE_DATA(mlsvalidatetrans, struct cil_validatetrans)
{
    cmp_hash_update_string(full_hash, mlsvalidatetrans->class_str);
    *partial_hash = cmp_hash_copy(full_hash);
    char expr_hash[HASH_SIZE];
    hash_cil_expr(mlsvalidatetrans->str_expr, expr_hash);
    cmp_hash_update(full_hash, HASH_SIZE, expr_hash);
}

/******************************************************************************
 *  Container Statements                                                      *
 ******************************************************************************/

DEFINE_DATA_SIMPLE_DECL(block, struct cil_block)

DEFINE_DATA(blockabstract, struct cil_blockabstract)
{
    UNUSED(partial_hash);
    cmp_hash_update_string(full_hash, blockabstract->block_str);
}

DEFINE_DATA(blockinherit, struct cil_blockinherit)
{
    UNUSED(partial_hash);
    cmp_hash_update_string(full_hash, blockinherit->block_str);
}

DEFINE_DATA(optional, struct cil_optional)
{
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update_string(full_hash, optional->datum.name);
}

DEFINE_DATA(in, struct cil_in)
{
    UNUSED(partial_hash);
    cmp_hash_update(full_hash, sizeof(in->is_after), &in->is_after);
    cmp_hash_update_string(full_hash, in->block_str);
}

/******************************************************************************
 *  Context Statement                                                         *
 ******************************************************************************/

DEFINE_DATA(context, struct cil_context)
{
    if (context->datum.name) {
        cmp_hash_update_string(full_hash, context->datum.name);
    } else {
        cmp_hash_update_string(full_hash, "<anonymous::context>");
    }
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update_string(full_hash, context->user_str);
    cmp_hash_update_string(full_hash, context->role_str);
    cmp_hash_update_string(full_hash, context->type_str);
    hash_str_or_data(full_hash, CIL_LEVELRANGE, context->range_str,
                     context->range);
}

/******************************************************************************
 *  Default Object Statements                                                 *
 ******************************************************************************/

DEFINE_DATA(cil_default, struct cil_default)
{
    cmp_hash_update(full_hash, sizeof(cil_default->flavor),
                    &cil_default->flavor);
    cmp_hash_update(full_hash, sizeof(cil_default->object),
                    &cil_default->object);
    *partial_hash = cmp_hash_copy(full_hash);
    char class_hash[HASH_SIZE];
    hash_cil_string_list(cil_default->class_strs, LIST_ORDER_UNORDERED,
                         class_hash);
    cmp_hash_update(full_hash, HASH_SIZE, class_hash);
}

DEFINE_DATA(defaultrange, struct cil_defaultrange)
{
    cmp_hash_update(full_hash, sizeof(defaultrange->object_range),
                    &defaultrange->object_range);
    *partial_hash = cmp_hash_copy(full_hash);
    char class_hash[HASH_SIZE];
    hash_cil_string_list(defaultrange->class_strs, LIST_ORDER_UNORDERED,
                         class_hash);
    cmp_hash_update(full_hash, HASH_SIZE, class_hash);
}

/******************************************************************************
 *  File Labeling Statements                                                  *
 ******************************************************************************/

DEFINE_DATA(filecon, struct cil_filecon)
{
    cmp_hash_update_string(full_hash, filecon->path_str);
    cmp_hash_update(full_hash, sizeof(filecon->type), &filecon->type);
    *partial_hash = cmp_hash_copy(full_hash);
    if (filecon->context_str || filecon->context) {
        cmp_hash_update_string(full_hash, "<context>");
        hash_str_or_data(full_hash, CIL_CONTEXT, filecon->context_str,
                         filecon->context);
    } else {
        cmp_hash_update_string(full_hash, "<empty_context>");
    }
}

DEFINE_DATA(fsuse, struct cil_fsuse)
{
    UNUSED(partial_hash);
    cmp_hash_update(full_hash, sizeof(fsuse->type), &fsuse->type);
    cmp_hash_update_string(full_hash, fsuse->fs_str);
    hash_str_or_data(full_hash, CIL_CONTEXT, fsuse->context_str,
                     fsuse->context);
}

DEFINE_DATA(genfscon, struct cil_genfscon)
{
    cmp_hash_update_string(full_hash, genfscon->fs_str);
    cmp_hash_update_string(full_hash, genfscon->path_str);
    cmp_hash_update(full_hash, sizeof(genfscon->file_type),
                    &genfscon->file_type);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_CONTEXT, genfscon->context_str,
                     genfscon->context);
}

/******************************************************************************
 *  Infiniband Statements                                                     *
 ******************************************************************************/

DEFINE_DATA(ibpkeycon, struct cil_ibpkeycon)
{
    cmp_hash_update_string(full_hash, ibpkeycon->subnet_prefix_str);
    cmp_hash_update(full_hash, sizeof(ibpkeycon->pkey_low),
                    &ibpkeycon->pkey_low);
    cmp_hash_update(full_hash, sizeof(ibpkeycon->pkey_low),
                    &ibpkeycon->pkey_low);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_CONTEXT, ibpkeycon->context_str,
                     ibpkeycon->context);
}

DEFINE_DATA(ibendportcon, struct cil_ibendportcon)
{
    cmp_hash_update_string(full_hash, ibendportcon->dev_name_str);
    cmp_hash_update(full_hash, sizeof(ibendportcon->port), &ibendportcon->port);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_CONTEXT, ibendportcon->context_str,
                     ibendportcon->context);
}

/******************************************************************************
 *  Multi-Level Security Labeling Statements                                  *
 ******************************************************************************/

DEFINE_DATA_SIMPLE_DECL(sensitivity, struct cil_sens)
DEFINE_DATA_ALIAS(sensitivityalias)
DEFINE_DATA_ALIAS_ACTUAL(sensitivityaliasactual)
DEFINE_DATA_ORDERED(sensitivityorder, LIST_ORDER_ORDERED)
DEFINE_DATA_SIMPLE_DECL(category, struct cil_cat)
DEFINE_DATA_ALIAS(categoryalias)
DEFINE_DATA_ALIAS_ACTUAL(categoryaliasactual)
DEFINE_DATA_ORDERED(categoryorder, LIST_ORDER_ORDERED)

DEFINE_DATA(categoryset, struct cil_catset)
{
    if (categoryset->datum.name) {
        cmp_hash_update_string(full_hash, categoryset->datum.name);
    } else {
        cmp_hash_update_string(full_hash, "<anonymous::categoryset>");
    }
    *partial_hash = cmp_hash_copy(full_hash);
    char cats_hash[HASH_SIZE];
    hash_cil_expr(categoryset->cats->str_expr, cats_hash);
    cmp_hash_update(full_hash, HASH_SIZE, cats_hash);
}

DEFINE_DATA(sensitivitycategory, struct cil_senscat)
{
    cmp_hash_update_string(full_hash, sensitivitycategory->sens_str);
    *partial_hash = cmp_hash_copy(full_hash);
    char cats_hash[HASH_SIZE];
    hash_cil_expr(sensitivitycategory->cats->str_expr, cats_hash);
    cmp_hash_update(full_hash, HASH_SIZE, cats_hash);
}

DEFINE_DATA(level, struct cil_level)
{
    if (level->datum.name) {
        cmp_hash_update_string(full_hash, level->datum.name);
    } else {
        cmp_hash_update_string(full_hash, "<anonymous::level>");
    }
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update_string(full_hash, level->sens_str);
    if (level->cats) {
        char cats_hash[HASH_SIZE];
        hash_cil_expr(level->cats->str_expr, cats_hash);
        cmp_hash_update(full_hash, HASH_SIZE, cats_hash);
    }
}

DEFINE_DATA(levelrange, struct cil_levelrange)
{
    if (levelrange->datum.name) {
        cmp_hash_update_string(full_hash, levelrange->datum.name);
    } else {
        cmp_hash_update_string(full_hash, "<anonymous::levelrange>");
    }
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_LEVEL, levelrange->low_str,
                     levelrange->low);
    hash_str_or_data(full_hash, CIL_LEVEL, levelrange->high_str,
                     levelrange->high);
}

DEFINE_DATA(rangetransition, struct cil_rangetransition)
{
    cmp_hash_update_string(full_hash, rangetransition->src_str);
    cmp_hash_update_string(full_hash, rangetransition->exec_str);
    cmp_hash_update_string(full_hash, rangetransition->obj_str);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_LEVELRANGE, rangetransition->range_str,
                     rangetransition->range);
}

/******************************************************************************
 *  Network Labeling Statements                                               *
 ******************************************************************************/

DEFINE_DATA(ipaddr, struct cil_ipaddr)
{
    if (ipaddr->datum.name) {
        cmp_hash_update_string(full_hash, ipaddr->datum.name);
    } else {
        cmp_hash_update_string(full_hash, "<anonymous::ipaddr>");
    }
    *partial_hash = cmp_hash_copy(full_hash);
    switch (ipaddr->family) {
    case AF_INET:
        cmp_hash_update(full_hash, sizeof(ipaddr->ip.v4), &ipaddr->ip.v4);
        break;
    case AF_INET6:
        cmp_hash_update(full_hash, sizeof(ipaddr->ip.v6), &ipaddr->ip.v6);
        break;
    default:
        assert(false /* Invalid IP address family */);
    }
}

DEFINE_DATA(netifcon, struct cil_netifcon)
{
    cmp_hash_update_string(full_hash, netifcon->interface_str);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_CONTEXT, netifcon->if_context_str,
                     netifcon->if_context);
    hash_str_or_data(full_hash, CIL_CONTEXT, netifcon->packet_context_str,
                     netifcon->packet_context);
}

DEFINE_DATA(nodecon, struct cil_nodecon)
{
    hash_str_or_data(full_hash, CIL_IPADDR, nodecon->addr_str, nodecon->addr);
    hash_str_or_data(full_hash, CIL_IPADDR, nodecon->mask_str, nodecon->mask);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_CONTEXT, nodecon->context_str,
                     nodecon->context);
}

DEFINE_DATA(portcon, struct cil_portcon)
{
    cmp_hash_update(full_hash, sizeof(portcon->proto), &portcon->proto);
    cmp_hash_update(full_hash, sizeof(portcon->port_low), &portcon->port_low);
    cmp_hash_update(full_hash, sizeof(portcon->port_high), &portcon->port_high);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_CONTEXT, portcon->context_str,
                     portcon->context);
}

/******************************************************************************
 *  Policy Configuration Statements                                           *
 ******************************************************************************/

DEFINE_DATA(mls, struct cil_mls)
{
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update(full_hash, sizeof(mls->value), &mls->value);
}

DEFINE_DATA(handleunknown, struct cil_handleunknown)
{
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update(full_hash, sizeof(handleunknown->handle_unknown),
                    &handleunknown->handle_unknown);
}
DEFINE_DATA_SIMPLE_DECL(policycap, struct cil_policycap)

/******************************************************************************
 *  Role Statements                                                           *
 ******************************************************************************/

DEFINE_DATA_SIMPLE_DECL(role, struct cil_role)

DEFINE_DATA(roletype, struct cil_roletype)
{
    cmp_hash_update_string(full_hash, roletype->role_str);
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update_string(full_hash, roletype->type_str);
}
DEFINE_DATA_SIMPLE_DECL(roleattribute, struct cil_roleattribute)
DEFINE_DATA_ATTRIBUTESET(roleattributeset, struct cil_roleattributeset)

DEFINE_DATA(roleallow, struct cil_roleallow)
{
    cmp_hash_update_string(full_hash, roleallow->src_str);
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update_string(full_hash, roleallow->tgt_str);
}

DEFINE_DATA(roletransition, struct cil_roletransition)
{
    cmp_hash_update_string(full_hash, roletransition->src_str);
    cmp_hash_update_string(full_hash, roletransition->tgt_str);
    cmp_hash_update_string(full_hash, roletransition->obj_str);
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update_string(full_hash, roletransition->result_str);
}
DEFINE_DATA_BOUNDS(rolebounds)

/******************************************************************************
 *  SID Statements                                                            *
 ******************************************************************************/

DEFINE_DATA_SIMPLE_DECL(sid, struct cil_sid)
DEFINE_DATA_ORDERED(sidorder, LIST_ORDER_ORDERED)

DEFINE_DATA(sidcontext, struct cil_sidcontext)
{
    cmp_hash_update_string(full_hash, sidcontext->sid_str);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_CONTEXT, sidcontext->context_str,
                     sidcontext->context);
}

/******************************************************************************
 *  Type Statements                                                           *
 ******************************************************************************/

DEFINE_DATA_SIMPLE_DECL(type, struct cil_type)
DEFINE_DATA_ALIAS(typealias)
DEFINE_DATA_ALIAS_ACTUAL(typealiasactual)
DEFINE_DATA_SIMPLE_DECL(typeattribute, struct cil_typeattribute)
DEFINE_DATA_ATTRIBUTESET(typeattributeset, struct cil_typeattributeset)

DEFINE_DATA(expandtypeattribute, struct cil_expandtypeattribute)
{
    cmp_hash_update(full_hash, sizeof(expandtypeattribute->expand),
                    &expandtypeattribute->expand);
    *partial_hash = cmp_hash_copy(full_hash);
    char attrs_hash[HASH_SIZE];
    hash_cil_string_list(expandtypeattribute->attr_strs, LIST_ORDER_UNORDERED,
                         attrs_hash);
    cmp_hash_update(full_hash, HASH_SIZE, attrs_hash);
}
DEFINE_DATA_BOUNDS(typebounds)

DEFINE_DATA(type_rule, struct cil_type_rule)
{
    cmp_hash_update(full_hash, sizeof(type_rule->rule_kind),
                    &type_rule->rule_kind);
    cmp_hash_update_string(full_hash, type_rule->src_str);
    cmp_hash_update_string(full_hash, type_rule->tgt_str);
    cmp_hash_update_string(full_hash, type_rule->obj_str);
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update_string(full_hash, type_rule->result_str);
}

DEFINE_DATA(nametypetransition, struct cil_nametypetransition)
{
    cmp_hash_update_string(full_hash, nametypetransition->src_str);
    cmp_hash_update_string(full_hash, nametypetransition->tgt_str);
    cmp_hash_update_string(full_hash, nametypetransition->obj_str);
    cmp_hash_update_string(full_hash, nametypetransition->name_str);
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update_string(full_hash, nametypetransition->result_str);
}

DEFINE_DATA(typepermissive, struct cil_typepermissive)
{
    UNUSED(partial_hash);
    cmp_hash_update_string(full_hash, typepermissive->type_str);
}

/******************************************************************************
 *  User Statements                                                           *
 ******************************************************************************/

DEFINE_DATA_SIMPLE_DECL(user, struct cil_user)

DEFINE_DATA(userrole, struct cil_userrole)
{
    cmp_hash_update_string(full_hash, userrole->user_str);
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update_string(full_hash, userrole->role_str);
}
DEFINE_DATA_SIMPLE_DECL(userattribute, struct cil_userattribute)
DEFINE_DATA_ATTRIBUTESET(userattributeset, struct cil_userattributeset)

DEFINE_DATA(userlevel, struct cil_userlevel)
{
    cmp_hash_update_string(full_hash, userlevel->user_str);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_LEVEL, userlevel->level_str,
                     userlevel->level);
}

DEFINE_DATA(userrange, struct cil_userrange)
{
    cmp_hash_update_string(full_hash, userrange->user_str);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_LEVELRANGE, userrange->range_str,
                     userrange->range);
}
DEFINE_DATA_BOUNDS(userbounds)

DEFINE_DATA(userprefix, struct cil_userprefix)
{
    cmp_hash_update_string(full_hash, userprefix->user_str);
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update_string(full_hash, userprefix->prefix_str);
}

DEFINE_DATA(selinuxuser, struct cil_selinuxuser)
{
    cmp_hash_update_string(full_hash, selinuxuser->name_str);
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update_string(full_hash, selinuxuser->user_str);
    hash_str_or_data(full_hash, CIL_LEVELRANGE, selinuxuser->range_str,
                     selinuxuser->range);
}

DEFINE_DATA(selinuxuserdefault, struct cil_selinuxuser)
{
    *partial_hash = cmp_hash_copy(full_hash);
    cmp_hash_update_string(full_hash, selinuxuserdefault->user_str);
    hash_str_or_data(full_hash, CIL_LEVELRANGE, selinuxuserdefault->range_str,
                     selinuxuserdefault->range);
}

/******************************************************************************
 *  Xen Statements                                                            *
 ******************************************************************************/

DEFINE_DATA(iomemcon, struct cil_iomemcon)
{
    cmp_hash_update(full_hash, sizeof(iomemcon->iomem_low),
                    &iomemcon->iomem_low);
    cmp_hash_update(full_hash, sizeof(iomemcon->iomem_high),
                    &iomemcon->iomem_high);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_CONTEXT, iomemcon->context_str,
                     iomemcon->context);
}

DEFINE_DATA(ioportcon, struct cil_ioportcon)
{
    cmp_hash_update(full_hash, sizeof(ioportcon->ioport_low),
                    &ioportcon->ioport_low);
    cmp_hash_update(full_hash, sizeof(ioportcon->ioport_high),
                    &ioportcon->ioport_high);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_CONTEXT, ioportcon->context_str,
                     ioportcon->context);
}

DEFINE_DATA(pcidevicecon, struct cil_pcidevicecon)
{
    cmp_hash_update(full_hash, sizeof(pcidevicecon->dev), &pcidevicecon->dev);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_CONTEXT, pcidevicecon->context_str,
                     pcidevicecon->context);
}

DEFINE_DATA(pirqcon, struct cil_pirqcon)
{
    cmp_hash_update(full_hash, sizeof(pirqcon->pirq), &pirqcon->pirq);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_CONTEXT, pirqcon->context_str,
                     pirqcon->context);
}

DEFINE_DATA(devicetreecon, struct cil_devicetreecon)
{
    cmp_hash_update_string(full_hash, devicetreecon->path);
    *partial_hash = cmp_hash_copy(full_hash);
    hash_str_or_data(full_hash, CIL_CONTEXT, devicetreecon->context_str,
                     devicetreecon->context);
}

static const struct cmp_data_def data_defs[] = {
    /* Common and Utility Nodes */
    [CIL_ROOT] = { REGISTER_DATA(root) },
    [CIL_SRC_INFO] = { REGISTER_DATA(src_info) },
    [CIL_STRING] = { REGISTER_DATA(string) },
    /* Access Vector Rules */
    [CIL_AVRULE] = { REGISTER_DATA(avrule) },
    [CIL_AVRULEX] = { REGISTER_DATA(avrule) },
    [CIL_DENY_RULE] = { REGISTER_DATA(deny) },
    /* Call / Macro Statements */
    [CIL_CALL] = { REGISTER_DATA(call) },
    [CIL_MACRO] = { REGISTER_DATA(macro) },
    /* Class and Permission Statements */
    [CIL_PERM] = { REGISTER_DATA(perm) },
    [CIL_MAP_PERM] = { REGISTER_DATA(perm) },
    [CIL_COMMON] = { REGISTER_DATA(common) },
    [CIL_CLASSCOMMON] = { REGISTER_DATA(classcommon) },
    [CIL_CLASS] = { REGISTER_DATA(class) },
    [CIL_CLASSORDER] = { REGISTER_DATA(classorder) },
    [CIL_CLASSPERMISSION] = { REGISTER_DATA(classpermission) },
    [CIL_CLASSPERMS_SET] = { REGISTER_DATA(classperms_set) },
    [CIL_CLASSPERMISSIONSET] = { REGISTER_DATA(classpermissionset) },
    [CIL_MAP_CLASS] = { REGISTER_DATA(classmap) },
    [CIL_CLASSMAPPING] = { REGISTER_DATA(classmapping) },
    [CIL_PERMISSIONX] = { REGISTER_DATA(permissionx) },
    [CIL_CLASSPERMS] = { REGISTER_DATA(classperms) },
    /* Conditional Statements */
    [CIL_BOOL] = { REGISTER_DATA(boolean) },
    [CIL_BOOLEANIF] = { REGISTER_DATA(booleanif) },
    [CIL_TUNABLE] = { REGISTER_DATA(tunable) },
    [CIL_TUNABLEIF] = { REGISTER_DATA(tunableif) },
    /* Constaint Statements */
    [CIL_CONSTRAIN] = { REGISTER_DATA(constrain) },
    [CIL_VALIDATETRANS] = { REGISTER_DATA(validatetrans) },
    [CIL_MLSCONSTRAIN] = { REGISTER_DATA(mlsconstrain) },
    [CIL_MLSVALIDATETRANS] = { REGISTER_DATA(mlsvalidatetrans) },
    /* Container Statements */
    [CIL_BLOCK] = { REGISTER_DATA(block) },
    [CIL_BLOCKABSTRACT] = { REGISTER_DATA(blockabstract) },
    [CIL_BLOCKINHERIT] = { REGISTER_DATA(blockinherit) },
    [CIL_OPTIONAL] = { REGISTER_DATA(optional) },
    [CIL_IN] = { REGISTER_DATA(in) },
    /* Context Statement */
    [CIL_CONTEXT] = { REGISTER_DATA(context) },
    /* Default Object Statements */
    [CIL_DEFAULTUSER] = { REGISTER_DATA(cil_default) },
    [CIL_DEFAULTROLE] = { REGISTER_DATA(cil_default) },
    [CIL_DEFAULTTYPE] = { REGISTER_DATA(cil_default) },
    [CIL_DEFAULTRANGE] = { REGISTER_DATA(defaultrange) },
    /* File Labeling Statements */
    [CIL_FILECON] = { REGISTER_DATA(filecon) },
    [CIL_FSUSE] = { REGISTER_DATA(fsuse) },
    [CIL_GENFSCON] = { REGISTER_DATA(genfscon) },
    /* Infiniband Statements */
    [CIL_IBPKEYCON] = { REGISTER_DATA(ibpkeycon) },
    [CIL_IBENDPORTCON] = { REGISTER_DATA(ibendportcon) },
    /* Multi-Level Security Labeling Statements */
    [CIL_SENS] = { REGISTER_DATA(sensitivity) },
    [CIL_SENSALIAS] = { REGISTER_DATA(sensitivityalias) },
    [CIL_SENSALIASACTUAL] = { REGISTER_DATA(sensitivityaliasactual) },
    [CIL_SENSITIVITYORDER] = { REGISTER_DATA(sensitivityorder) },
    [CIL_CAT] = { REGISTER_DATA(category) },
    [CIL_CATALIAS] = { REGISTER_DATA(categoryalias) },
    [CIL_CATALIASACTUAL] = { REGISTER_DATA(categoryaliasactual) },
    [CIL_CATORDER] = { REGISTER_DATA(categoryorder) },
    [CIL_CATSET] = { REGISTER_DATA(categoryset) },
    [CIL_SENSCAT] = { REGISTER_DATA(sensitivitycategory) },
    [CIL_LEVEL] = { REGISTER_DATA(level) },
    [CIL_LEVELRANGE] = { REGISTER_DATA(levelrange) },
    [CIL_RANGETRANSITION] = { REGISTER_DATA(rangetransition) },
    /* Network Labeling Statements */
    [CIL_IPADDR] = { REGISTER_DATA(ipaddr) },
    [CIL_NETIFCON] = { REGISTER_DATA(netifcon) },
    [CIL_NODECON] = { REGISTER_DATA(nodecon) },
    [CIL_PORTCON] = { REGISTER_DATA(portcon) },
    /* Policy Configuration Statements */
    [CIL_MLS] = { REGISTER_DATA(mls) },
    [CIL_HANDLEUNKNOWN] = { REGISTER_DATA(handleunknown) },
    [CIL_POLICYCAP] = { REGISTER_DATA(policycap) },
    /* Role Statements */
    [CIL_ROLE] = { REGISTER_DATA(role) },
    [CIL_ROLETYPE] = { REGISTER_DATA(roletype) },
    [CIL_ROLEATTRIBUTE] = { REGISTER_DATA(roleattribute) },
    [CIL_ROLEATTRIBUTESET] = { REGISTER_DATA(roleattributeset) },
    [CIL_ROLEALLOW] = { REGISTER_DATA(roleallow) },
    [CIL_ROLETRANSITION] = { REGISTER_DATA(roletransition) },
    [CIL_ROLEBOUNDS] = { REGISTER_DATA(rolebounds) },
    /* SID Statements */
    [CIL_SID] = { REGISTER_DATA(sid) },
    [CIL_SIDORDER] = { REGISTER_DATA(sidorder) },
    [CIL_SIDCONTEXT] = { REGISTER_DATA(sidcontext) },
    /* Type Statements */
    [CIL_TYPE] = { REGISTER_DATA(type) },
    [CIL_TYPEALIAS] = { REGISTER_DATA(typealias) },
    [CIL_TYPEALIASACTUAL] = { REGISTER_DATA(typealiasactual) },
    [CIL_TYPEATTRIBUTE] = { REGISTER_DATA(typeattribute) },
    [CIL_TYPEATTRIBUTESET] = { REGISTER_DATA(typeattributeset) },
    [CIL_EXPANDTYPEATTRIBUTE] = { REGISTER_DATA(expandtypeattribute) },
    [CIL_TYPEBOUNDS] = { REGISTER_DATA(typebounds) },
    [CIL_TYPE_RULE] = { REGISTER_DATA(type_rule) },
    [CIL_NAMETYPETRANSITION] = { REGISTER_DATA(nametypetransition) },
    [CIL_TYPEPERMISSIVE] = { REGISTER_DATA(typepermissive) },
    /* User Statements */
    [CIL_USER] = { REGISTER_DATA(user) },
    [CIL_USERROLE] = { REGISTER_DATA(userrole) },
    [CIL_USERATTRIBUTE] = { REGISTER_DATA(userattribute) },
    [CIL_USERATTRIBUTESET] = { REGISTER_DATA(userattributeset) },
    [CIL_USERLEVEL] = { REGISTER_DATA(userlevel) },
    [CIL_USERRANGE] = { REGISTER_DATA(userrange) },
    [CIL_USERBOUNDS] = { REGISTER_DATA(userbounds) },
    [CIL_USERPREFIX] = { REGISTER_DATA(userprefix) },
    [CIL_SELINUXUSER] = { REGISTER_DATA(selinuxuser) },
    [CIL_SELINUXUSERDEFAULT] = { REGISTER_DATA(selinuxuserdefault) },
    /* Xen Statements */
    [CIL_IOMEMCON] = { REGISTER_DATA(iomemcon) },
    [CIL_IOPORTCON] = { REGISTER_DATA(ioportcon) },
    [CIL_PCIDEVICECON] = { REGISTER_DATA(pcidevicecon) },
    [CIL_PIRQCON] = { REGISTER_DATA(pirqcon) },
    [CIL_DEVICETREECON] = { REGISTER_DATA(devicetreecon) },
};
#define DATA_DEFS_COUNT (sizeof(data_defs) / sizeof(*data_defs))

void cmp_data_init(enum cil_flavor flavor, const void *cil_data,
                   struct cmp_data *cmp_data)
{
    if (flavor >= DATA_DEFS_COUNT || !data_defs[flavor].init) {
        error(EXIT_FAILURE, 0, "Encountered an unknown node type %d", flavor);
    }
    const struct cmp_data_def *def = &data_defs[flavor];

    struct cmp_hash_state *full_hash = cmp_hash_begin(def->flavor_name);
    struct cmp_hash_state *partial_hash = NULL;

    def->init(cil_data, full_hash, &partial_hash);
    *cmp_data = (struct cmp_data) {
        .flavor = flavor,
        .cil_data = cil_data,
    };
    cmp_hash_finish(full_hash, cmp_data->full_hash);
    if (partial_hash) {
        cmp_hash_finish(partial_hash, cmp_data->partial_hash);
    } else {
        memcpy(cmp_data->partial_hash, cmp_data->full_hash, HASH_SIZE);
    }
}
