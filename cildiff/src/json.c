#include "json.h"

#include <arpa/inet.h>
#include <assert.h>
#include <error.h>
#include <inttypes.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cil_flavor.h"
#include "cil_internal.h"
#include "cil_list.h"
#include "cil_tree.h"

#include "cmp_common.h"
#include "diff.h"
#include "utils.h"


/* JSON Utils */

static int inc_indent(int indent)
{
    return indent >= 0 ? indent + 1 : indent;
}

static int dec_indent(int indent)
{
    return indent >= 0 ? indent - 1 : indent;
}

static void json_print_indent(int indent, FILE *output)
{
    if (indent < 0) {
        fputc(' ', output);
        return;
    }
    fputc('\n', output);
    for (int i = 0; i < indent; i++) {
        fputs("    ", output);
    }
}

static int json_array_start(int indent, FILE *output)
{
    fputc('[', output);
    return inc_indent(indent);
}

static int json_array_end(int indent, FILE *output)
{
    indent = dec_indent(indent);
    json_print_indent(indent, output);
    fputc(']', output);
    return indent;
}

static int json_object_start(int indent, FILE *output)
{
    fputc('{', output);
    return inc_indent(indent);
}

static int json_object_end(int indent, FILE *output)
{
    indent = dec_indent(indent);
    json_print_indent(indent, output);
    fputc('}', output);
    return indent;
}

static void json_print_next(FILE *output)
{
    fputc(',', output);
}

static void json_print_string(FILE *output, const char *string)
{
    fputc('"', output);
    for (size_t i = 0; string[i]; i++) {
        switch (string[i]) {
        case '\\':
        case '"':
            fputc('\\', output);
            break;
        }
        fputc(string[i], output);
    }
    fputc('"', output);
}

__attribute__ ((format(printf, 4, 5)))
static void json_print_kv(int indent, FILE *output, const char *key, const char *value_fmt, ...)
{
    json_print_indent(indent, output);
    json_print_string(output, key);
    fputs(": ", output);
    if (!value_fmt) {
        return;
    }
    va_list args;
    va_start(args);
    va_list tmp_args;
    va_copy(tmp_args, args);
    if (!strcmp(value_fmt, "%b")) {
        bool value = va_arg(tmp_args, int);
        fputs(value ? "true" : "false", output);
        goto exit;
    }
    if (!strcmp(value_fmt, "%s")) {
        const char *str = va_arg(tmp_args, const char *);
        if (!str) {
            fputs("null", output);
            goto exit;
        }
        json_print_string(output, str);
        goto exit;
    }
    vfprintf(output, value_fmt, args);
exit:
    va_end(tmp_args);
    va_end(args);
}


/* JSON Nodes */

struct json_cil_node_def {
    const char *type;
    void (*print_fn)(int indent, FILE *output, struct cil_tree_node *cil_node);
    const char *(*type_fn)(struct cil_tree_node *cil_node);
};

#define DEFINE_JSON_NODE(name, type) \
static void json_print_node_ ## name (int indent, FILE *output, struct cil_tree_node *cil_node, const type * name); \
static void json_print_node_ ## name ## _shim(int indent, FILE *output, struct cil_tree_node *cil_node) \
{ \
    json_print_node_ ## name (indent, output, cil_node, cil_node->data); \
} \
static void json_print_node_ ## name (int indent, FILE *output, struct cil_tree_node *cil_node, const type * name)

#define DEFINE_JSON_NODE_TYPE(name, type) \
static const char *json_node_type_ ## name (struct cil_tree_node *cil_node, const type * name); \
static const char *json_node_type_ ## name ## _shim(struct cil_tree_node *cil_node) \
{ \
    return json_node_type_ ## name (cil_node, cil_node->data); \
} \
static const char *json_node_type_ ## name (struct cil_tree_node *cil_node, const type * name)


#define REGISTER_JSON_NODE(name) \
.type = #name, .print_fn = json_print_node_ ## name ## _shim
#define REGISTER_JSON_NODE_TYPE(name) \
.type_fn = json_node_type_ ## name ## _shim


static void json_print_cil_node(int indent, FILE *output, struct cil_tree_node *cil_node);

static void json_print_cil_data(int indent, FILE *output, enum cil_flavor flavor, void *data, uint32_t line)
{
    if (!data) {
        json_print_indent(indent, output);
        fputs("null", output);
        return;
    }
    if (flavor == CIL_STRING) {
        json_print_indent(indent, output);
        json_print_string(output, data);
        return;
    }
    struct cil_tree_node cil_node = {
        .flavor = flavor,
        .data = data,
        .line = line,
    };
    json_print_cil_node(indent, output, &cil_node);
}

static void json_print_str_or_cil_data(int indent, FILE *output, const char *str, enum cil_flavor flavor, void *data, uint32_t line)
{
    if (str) {
        json_print_string(output, str);
    } else {
        json_print_cil_data(indent, output, flavor, data, line);
    }
}

static void json_print_cil_node_children(int indent, FILE *output, const char *key, struct cil_tree_node *cil_node)
{
    json_print_kv(indent, output, key ? key : "children", NULL);
    indent = json_array_start(indent, output);
    for (struct cil_tree_node *child = cil_node->cl_head; child; child = child->next) {
        json_print_indent(indent, output);
        json_print_cil_node(indent, output, child);
        if (child->next) {
            fputc(',', output);
        }
    }
    indent = json_array_end(indent, output);
}

static char **expr_op_keys[] = {
    [CIL_AND] = &CIL_KEY_AND,
    [CIL_OR] = &CIL_KEY_OR,
    [CIL_NOT] = &CIL_KEY_NOT,
    [CIL_ALL] = &CIL_KEY_ALL,
    [CIL_EQ] = &CIL_KEY_EQ,
    [CIL_NEQ] = &CIL_KEY_NEQ,
    [CIL_XOR] = &CIL_KEY_XOR,
    [CIL_RANGE] = &CIL_KEY_RANGE,
    [CIL_CONS_DOM] = &CIL_KEY_CONS_DOM,
    [CIL_CONS_DOMBY] = &CIL_KEY_CONS_DOMBY,
    [CIL_CONS_INCOMP] = &CIL_KEY_CONS_INCOMP,
    [CIL_CONS_U1] = &CIL_KEY_CONS_U1,
    [CIL_CONS_U2] = &CIL_KEY_CONS_U2,
    [CIL_CONS_U3] = &CIL_KEY_CONS_U3,
    [CIL_CONS_T1] = &CIL_KEY_CONS_T1,
    [CIL_CONS_T2] = &CIL_KEY_CONS_T2,
    [CIL_CONS_T3] = &CIL_KEY_CONS_T3,
    [CIL_CONS_R1] = &CIL_KEY_CONS_R1,
    [CIL_CONS_R2] = &CIL_KEY_CONS_R2,
    [CIL_CONS_R3] = &CIL_KEY_CONS_R3,
    [CIL_CONS_L1] = &CIL_KEY_CONS_L1,
    [CIL_CONS_L2] = &CIL_KEY_CONS_L2,
    [CIL_CONS_H1] = &CIL_KEY_CONS_H1,
    [CIL_CONS_H2] = &CIL_KEY_CONS_H2,
};

static void json_print_expr(int indent, FILE *output, const struct cil_list *expr)
{
    indent = json_object_start(indent, output);

    const struct cil_list_item *head = MAYBE(expr, head);
    const char *operator_str = NULL;
    if (head && head->flavor == CIL_OP) {
        operator_str = *(expr_op_keys[(uintptr_t)head->data]);
        head = head->next;
    }
    json_print_kv(indent, output, "operator", "%s", operator_str);
    json_print_next(output);
    json_print_kv(indent, output, "operands", NULL);
    indent = json_array_start(indent, output);
    for (const struct cil_list_item *item = head; item; item = item->next) {
        json_print_indent(indent, output);
        switch (item->flavor) {
        case CIL_STRING:
            json_print_string(output, item->data);
            break;
        case CIL_CONS_OPERAND:
            json_print_string(output, *(expr_op_keys[(uintptr_t)item->data]));
            break;
        case CIL_LIST:
            json_print_expr(indent, output, item->data);
            break;
        default:
            assert(false /* unreachable */);
        }
        if (item->next) {
            json_print_next(output);
        }
    }
    indent = json_array_end(indent, output);

    indent = json_object_end(indent, output);
}

/******************************************************************************
 *  Basic                                                                     *
 ******************************************************************************/

DEFINE_JSON_NODE(ordered, struct cil_ordered)
{
    (void)cil_node;
    bool unordered = false;
    const struct cil_list_item *head = ordered->strs->head;
    if (head->data == CIL_KEY_UNORDERED) {
        unordered = true;
        head = head->next;
    }
    json_print_kv(indent, output, "unordered", "%b", unordered);
    json_print_next(output);
    json_print_kv(indent, output, "order", NULL);
    indent = json_array_start(indent, output);
    for (const struct cil_list_item *item = head; item; item = item->next) {
        json_print_indent(indent, output);
        json_print_string(output, item->data);
        if (item->next) {
            json_print_next(output);
        }
    }
    indent = json_array_end(indent, output);
}

#define DEFINE_JSON_NODE_SIMPLE_DECL(decl_name, type) \
DEFINE_JSON_NODE(decl_name, struct cil_symtab_datum) \
{ \
    (void)cil_node; \
    static_assert(offsetof(type, datum) == 0, \
                  # decl_name " is not a simple CIL declaration"); \
    json_print_kv(indent, output, "id", "%s", decl_name->name); \
}

#define DEFINE_JSON_NODE_ALIAS_ACTUAL(decl_name, orig_name) \
DEFINE_JSON_NODE(decl_name, struct cil_aliasactual) \
{ \
    (void)cil_node; \
    json_print_kv(indent, output, orig_name "alias", "%s", decl_name->alias_str); \
    json_print_next(output); \
    json_print_kv(indent, output, orig_name, "%s", decl_name->actual_str); \
}

DEFINE_JSON_NODE(bounds, struct cil_bounds)
{
    (void)cil_node;
    json_print_kv(indent, output, "parent", "%s", bounds->parent_str);
    json_print_next(output);
    json_print_kv(indent, output, "child", "%s", bounds->child_str);
}

/******************************************************************************
 *  Access Vector Rules                                                       *
 ******************************************************************************/

DEFINE_JSON_NODE(avrule, struct cil_avrule)
{
    json_print_kv(indent, output, "source", "%s", avrule->src_str);
    json_print_next(output);
    json_print_kv(indent, output, "target", "%s", avrule->tgt_str);
    json_print_next(output);
    json_print_kv(indent, output, "classperms", NULL);
    if (avrule->is_extended) {
        json_print_str_or_cil_data(indent, output, avrule->perms.x.permx_str, CIL_PERMISSIONX, avrule->perms.x.permx, cil_node->line);
    } else {
        if (avrule->perms.classperms->head->flavor == CIL_CLASSPERMS_SET) {
            struct cil_classperms_set *classpermsset = avrule->perms.classperms->head->data;
            json_print_string(output, classpermsset->set_str);
        } else {
            json_print_cil_data(indent, output, avrule->perms.classperms->head->flavor, avrule->perms.classperms->head->data, cil_node->line);
        }
    }
}
DEFINE_JSON_NODE_TYPE(avrule, struct cil_avrule)
{
    (void)cil_node;
    assert(!avrule->is_extended);
    switch (avrule->rule_kind) {
    case CIL_AVRULE_ALLOWED:
        return CIL_KEY_ALLOW;
    case CIL_AVRULE_AUDITALLOW:
        return CIL_KEY_AUDITALLOW;
    case CIL_AVRULE_DONTAUDIT:
        return CIL_KEY_DONTAUDIT;
    case CIL_AVRULE_NEVERALLOW:
        return CIL_KEY_NEVERALLOW;
    }
    assert(false /* unreachable */);
}
DEFINE_JSON_NODE_TYPE(avrulex, struct cil_avrule)
{
    (void)cil_node;
    assert(avrulex->is_extended);
    switch (avrulex->rule_kind) {
    case CIL_AVRULE_ALLOWED:
        return CIL_KEY_ALLOWX;
    case CIL_AVRULE_AUDITALLOW:
        return CIL_KEY_AUDITALLOWX;
    case CIL_AVRULE_DONTAUDIT:
        return CIL_KEY_DONTAUDITX;
    case CIL_AVRULE_NEVERALLOW:
        return CIL_KEY_NEVERALLOWX;
    }
    assert(false /* unreachable */);
}
DEFINE_JSON_NODE(deny, struct cil_deny_rule)
{
    json_print_kv(indent, output, "source", "%s", deny->src_str);
    json_print_next(output);
    json_print_kv(indent, output, "target", "%s", deny->tgt_str);
    json_print_next(output);
    json_print_kv(indent, output, "classperms", NULL);
    if (deny->classperms->head->flavor == CIL_CLASSPERMS_SET) {
        struct cil_classperms_set *classpermsset = deny->classperms->head->data;
        json_print_string(output, classpermsset->set_str);
    } else {
        json_print_cil_data(indent, output, deny->classperms->head->flavor, deny->classperms->head->data, cil_node->line);
    }
}

/******************************************************************************
 *  Call / Macro Statements                                                   *
 ******************************************************************************/

static void print_call_args(struct cil_tree_node *cil_node, int indent, FILE *output)
{
    assert(!cil_node->cl_head != !cil_node->data);

    if (cil_node->data) {
        json_print_string(output, cil_node->data);
        return;
    }
    indent = json_array_start(indent, output);

    for (struct cil_tree_node *child = cil_node->cl_head; child; child = child->next) {
        json_print_indent(indent, output);
        print_call_args(child, indent, output);
        if (child->next) {
            json_print_next(output);
        }
    }

    indent = json_array_end(indent, output);
}
DEFINE_JSON_NODE(call, struct cil_call)
{
    (void)cil_node;
    json_print_kv(indent, output, "macro", "%s", call->macro_str);
    json_print_next(output);
    json_print_kv(indent, output, "args", NULL);
    print_call_args(call->args_tree->root, indent, output);
}
DEFINE_JSON_NODE(macro, struct cil_macro)
{
    json_print_kv(indent, output, "id", "%s", macro->datum.name);
    json_print_next(output);

    json_print_kv(indent, output, "params", NULL);
    indent = json_array_start(indent, output);
    for (const struct cil_list_item *item = macro->params->head; item; item = item->next) {
        const struct cil_param *param = item->data;
        json_print_indent(indent, output);
        indent = json_object_start(indent, output);
        struct cil_tree_node param_node = { .flavor = param->flavor };
        json_print_kv(indent, output, "type", "%s", cil_node_to_string(&param_node));
        json_print_next(output);
        json_print_kv(indent, output, "name", "%s", param->str);
        indent = json_object_end(indent, output);
        if (item->next) {
            json_print_next(output);
}
    }
    indent = json_array_end(indent, output);
    json_print_next(output);

    json_print_cil_node_children(indent, output, NULL, cil_node);
}

/******************************************************************************
 *  Class and Permission Statements                                           *
 ******************************************************************************/

DEFINE_JSON_NODE(classperms, struct cil_classperms)
{
    (void)cil_node;
    json_print_kv(indent, output, "class", "%s", classperms->class_str);
    json_print_next(output);
    json_print_kv(indent, output, "perms", NULL);
    json_print_expr(indent, output, classperms->perm_strs);
}
DEFINE_JSON_NODE_TYPE(common, struct cil_class)
{
    (void)cil_node;
    (void)common;
    return CIL_KEY_COMMON;
}
DEFINE_JSON_NODE(classcommon, struct cil_classcommon)
{
    (void)cil_node;
    json_print_kv(indent, output, "class", "%s", classcommon->class_str);
    json_print_next(output);
    json_print_kv(indent, output, "common", "%s", classcommon->common_str);
}
DEFINE_JSON_NODE(class, struct cil_class)
{
    json_print_kv(indent, output, "id", "%s", class->datum.name);
    json_print_next(output);
    json_print_kv(indent, output, "perms", NULL);
    indent = json_array_start(indent, output);
    for (const struct cil_tree_node *perm_node = cil_node->cl_head; perm_node; perm_node = perm_node->next) {
        assert(perm_node->flavor == CIL_PERM);
        const struct cil_perm *perm = perm_node->data;
        json_print_indent(indent, output);
        json_print_string(output, perm->datum.name);
        if (perm_node->next) {
            json_print_next(output);
        }
    }
    indent = json_array_end(indent, output);
}
DEFINE_JSON_NODE_TYPE(classorder, struct cil_ordered)
{
    (void)cil_node;
    (void)classorder;
    return CIL_KEY_CLASSORDER;
}
DEFINE_JSON_NODE_SIMPLE_DECL(classpermission, struct cil_classpermission)
DEFINE_JSON_NODE(classpermissionset, struct cil_classpermissionset)
{
    json_print_kv(indent, output, "id", "%s", classpermissionset->set_str);
    json_print_next(output);
    json_print_kv(indent, output, "classperms", NULL);
    assert(classpermissionset->classperms->head == classpermissionset->classperms->tail);
    assert(classpermissionset->classperms->head->flavor == CIL_CLASSPERMS);
    json_print_cil_data(indent, output, CIL_CLASSPERMS, classpermissionset->classperms->head->data, cil_node->line);
}
DEFINE_JSON_NODE(classmap, struct cil_class)
{
    json_print_kv(indent, output, "id", "%s", classmap->datum.name);
    json_print_next(output);
    json_print_kv(indent, output, "classmappings", NULL);
    indent = json_array_start(indent, output);
    for (const struct cil_tree_node *classmapping_node = cil_node->cl_head; classmapping_node; classmapping_node = classmapping_node->next) {
        assert(classmapping_node->flavor == CIL_MAP_PERM);
        const struct cil_perm *perm = classmapping_node->data;
        json_print_indent(indent, output);
        json_print_string(output, perm->datum.name);
        if (classmapping_node->next) {
            json_print_next(output);
        }
    }
    indent = json_array_end(indent, output);
}
DEFINE_JSON_NODE(classmapping, struct cil_classmapping)
{
    json_print_kv(indent, output, "classmap", "%s", classmapping->map_class_str);
    json_print_next(output);
    json_print_kv(indent, output, "classmapping", "%s", classmapping->map_perm_str);
    json_print_next(output);
    json_print_kv(indent, output, "classperms", NULL);
    assert(classmapping->classperms->head == classmapping->classperms->tail);
    if (classmapping->classperms->head->flavor == CIL_CLASSPERMS_SET) {
        struct cil_classperms_set *classpermsset = classmapping->classperms->head->data;
        json_print_string(output, classpermsset->set_str);
    } else {
        json_print_cil_data(indent, output, classmapping->classperms->head->flavor, classmapping->classperms->head->data, cil_node->line);
    }
}
DEFINE_JSON_NODE(permissionx, struct cil_permissionx)
{
    (void)cil_node;
    json_print_kv(indent, output, "id", "%s", permissionx->datum.name);
    json_print_next(output);
    const char *kind_str = NULL;
    switch (permissionx->kind) {
    case CIL_PERMX_KIND_IOCTL:
        kind_str = CIL_KEY_IOCTL;
        break;
    case CIL_PERMX_KIND_NLMSG:
        kind_str = CIL_KEY_NLMSG;
        break;
    default:
        assert(false /* unreachable */);
    }
    json_print_kv(indent, output, "kind", "%s", kind_str);
    json_print_next(output);
    json_print_kv(indent, output, "class", "%s", permissionx->obj_str);
    json_print_next(output);
    json_print_kv(indent, output, "perms", NULL);
    json_print_expr(indent, output, permissionx->expr_str);
}

/******************************************************************************
 *  Conditional Statements                                                    *
 ******************************************************************************/

DEFINE_JSON_NODE(boolean, struct cil_bool)
{
    (void)cil_node;
    json_print_kv(indent, output, "id", "%s", boolean->datum.name);
    json_print_next(output);
    json_print_kv(indent, output, "value", "%b", boolean->value);
}
DEFINE_JSON_NODE(booleanif, struct cil_booleanif)
{
    json_print_kv(indent, output, "condition", NULL);
    json_print_expr(indent, output, booleanif->str_expr);
    json_print_next(output);
    json_print_kv(indent, output, "branches", NULL);
    indent = json_array_start(indent, output);
    for (struct cil_tree_node *condblock_node = cil_node->cl_head; condblock_node; condblock_node = condblock_node->next) {
        assert(condblock_node->flavor == CIL_CONDBLOCK);
        const struct cil_condblock *condblock = condblock_node->data;
        json_print_indent(indent, output);
        indent = json_object_start(indent, output);
        json_print_kv(indent, output, "value", "%b", condblock->flavor == CIL_CONDTRUE);
        json_print_next(output);
        json_print_cil_node_children(indent, output, NULL, condblock_node);
        indent = json_object_end(indent, output);
        if (condblock_node->next) {
            json_print_next(output);
        }
    }
    indent = json_array_end(indent, output);
}
DEFINE_JSON_NODE(tunable, struct cil_tunable)
{
    (void)cil_node;
    json_print_kv(indent, output, "id", "%s", tunable->datum.name);
    json_print_next(output);
    json_print_kv(indent, output, "value", "%b", tunable->value);
}
DEFINE_JSON_NODE(tunableif, struct cil_tunableif)
{
    json_print_kv(indent, output, "condition", NULL);
    json_print_expr(indent, output, tunableif->str_expr);
    json_print_next(output);
    json_print_kv(indent, output, "branches", NULL);
    indent = json_array_start(indent, output);
    for (struct cil_tree_node *condblock_node = cil_node->cl_head; condblock_node; condblock_node = condblock_node->next) {
        assert(condblock_node->flavor == CIL_CONDBLOCK);
        const struct cil_condblock *condblock = condblock_node->data;
        json_print_indent(indent, output);
        indent = json_object_start(indent, output);
        json_print_kv(indent, output, "value", "%b", condblock->flavor == CIL_CONDTRUE);
        json_print_next(output);
        json_print_cil_node_children(indent, output, NULL, condblock_node);
        indent = json_object_end(indent, output);
        if (condblock_node->next) {
            json_print_next(output);
        }
    }
    indent = json_array_end(indent, output);
}

/******************************************************************************
 *  Constaint Statements                                                      *
 ******************************************************************************/

DEFINE_JSON_NODE(constrain, struct cil_constrain)
{
    json_print_kv(indent, output, "classperms", NULL);
    assert(constrain->classperms->head == constrain->classperms->tail);
    if (constrain->classperms->head->flavor == CIL_CLASSPERMS_SET) {
        struct cil_classperms_set *classpermsset = constrain->classperms->head->data;
        json_print_string(output, classpermsset->set_str);
    } else {
        json_print_cil_data(indent, output, constrain->classperms->head->flavor, constrain->classperms->head->data, cil_node->line);
    }
    json_print_next(output);
    json_print_kv(indent, output, "constraint", NULL);
    json_print_expr(indent, output, constrain->str_expr);
}
DEFINE_JSON_NODE(validatetrans, struct cil_validatetrans)
{
    (void)cil_node;
    json_print_kv(indent, output, "class", "%s", validatetrans->class_str);
    json_print_next(output);
    json_print_kv(indent, output, "constraint", NULL);
    json_print_expr(indent, output, validatetrans->str_expr);
}
DEFINE_JSON_NODE_TYPE(mlsconstrain, struct cil_constrain)
{
    (void)mlsconstrain;
    (void)cil_node;
    return CIL_KEY_MLSCONSTRAIN;
}
DEFINE_JSON_NODE_TYPE(mlsvalidatetrans, struct cil_validatetrans)
{
    (void)mlsvalidatetrans;
    (void)cil_node;
    return CIL_KEY_MLSVALIDATETRANS;
}

/******************************************************************************
 *  Container Statements                                                      *
 ******************************************************************************/

DEFINE_JSON_NODE(block, struct cil_block)
{
    json_print_kv(indent, output, "id", "%s", block->datum.name);
    json_print_next(output);
    json_print_cil_node_children(indent, output, NULL, cil_node);
}
DEFINE_JSON_NODE(blockabstract, struct cil_blockabstract)
{
    (void)cil_node;
    json_print_kv(indent, output, "id", "%s", blockabstract->block_str);
}
DEFINE_JSON_NODE(blockinherit, struct cil_blockinherit)
{
    (void)cil_node;
    json_print_kv(indent, output, "template", "%s", blockinherit->block_str);
}
DEFINE_JSON_NODE(optional, struct cil_optional)
{
    json_print_kv(indent, output, "id", "%s", optional->datum.name);
    json_print_next(output);
    json_print_cil_node_children(indent, output, NULL, cil_node);
}
DEFINE_JSON_NODE(in, struct cil_in)
{
    json_print_kv(indent, output, "position", "%s", in->is_after ? CIL_KEY_IN_AFTER : CIL_KEY_IN_BEFORE);
    json_print_next(output);
    json_print_kv(indent, output, "container", "%s", in->block_str);
    json_print_next(output);
    json_print_cil_node_children(indent, output, NULL, cil_node);
}

/******************************************************************************
 *  Context Statement                                                         *
 ******************************************************************************/

DEFINE_JSON_NODE(context, struct cil_context)
{
    json_print_kv(indent, output, "id", "%s", context->datum.name);
    json_print_next(output);
    json_print_kv(indent, output, "user", "%s", context->user_str);
    json_print_next(output);
    json_print_kv(indent, output, "role", "%s", context->role_str);
    json_print_next(output);
    json_print_kv(indent, output, "type", "%s", context->type_str);
    json_print_next(output);
    json_print_kv(indent, output, "levelrange", NULL);
    json_print_str_or_cil_data(indent, output, context->range_str, CIL_LEVELRANGE, context->range, cil_node->line);
}

/******************************************************************************
 *  Default Object Statements                                                 *
 ******************************************************************************/

DEFINE_JSON_NODE(cil_default, struct cil_default)
{
    (void)cil_node;
    json_print_kv(indent, output, "class", NULL);
    indent = json_array_start(indent, output);
    for (const struct cil_list_item *class_item = cil_default->class_strs->head; class_item; class_item = class_item->next) {
        json_print_indent(indent, output);
        json_print_string(output, class_item->data);
        if (class_item->next) {
            json_print_next(output);
        }
    }
    indent = json_array_end(indent, output);
    json_print_next(output);
    const char *default_str = NULL;
    switch (cil_default->object) {
    case CIL_DEFAULT_SOURCE:
        default_str = CIL_KEY_SOURCE;
        break;
    case CIL_DEFAULT_TARGET:
        default_str = CIL_KEY_TARGET;
        break;
    }
    json_print_kv(indent, output, "default", "%s", default_str);
}
DEFINE_JSON_NODE_TYPE(cil_default, struct cil_default)
{
    (void)cil_node;
    switch (cil_default->flavor) {
    case CIL_DEFAULTUSER:
        return CIL_KEY_DEFAULTUSER;
    case CIL_DEFAULTROLE:
        return CIL_KEY_DEFAULTROLE;
    case CIL_DEFAULTTYPE:
        return CIL_KEY_DEFAULTTYPE;
    default:
        assert(false /* unreachable */);
    }
}
DEFINE_JSON_NODE(defaultrange, struct cil_defaultrange)
{
    (void)cil_node;
    json_print_kv(indent, output, "class", NULL);
    indent = json_array_start(indent, output);
    for (const struct cil_list_item *class_item = defaultrange->class_strs->head; class_item; class_item = class_item->next) {
        json_print_indent(indent, output);
        json_print_string(output, class_item->data);
        if (class_item->next) {
            json_print_next(output);
        }
    }
    indent = json_array_end(indent, output);
    json_print_next(output);
    const char *default_str = NULL;
    switch (defaultrange->object_range) {
    case CIL_DEFAULT_SOURCE_LOW:
    case CIL_DEFAULT_SOURCE_HIGH:
    case CIL_DEFAULT_SOURCE_LOW_HIGH:
        default_str = CIL_KEY_SOURCE;
        break;
    case CIL_DEFAULT_TARGET_LOW:
    case CIL_DEFAULT_TARGET_HIGH:
    case CIL_DEFAULT_TARGET_LOW_HIGH:
        default_str = CIL_KEY_TARGET;
        break;
    case CIL_DEFAULT_GLBLUB:
        default_str = CIL_KEY_GLBLUB;
        break;
    }
    const char *range_str = NULL;
    switch (defaultrange->object_range) {
    case CIL_DEFAULT_SOURCE_LOW:
    case CIL_DEFAULT_TARGET_LOW:
        range_str = CIL_KEY_LOW;
        break;
    case CIL_DEFAULT_TARGET_HIGH:
    case CIL_DEFAULT_SOURCE_HIGH:
        range_str = CIL_KEY_HIGH;
        break;
    case CIL_DEFAULT_TARGET_LOW_HIGH:
    case CIL_DEFAULT_SOURCE_LOW_HIGH:
        range_str = CIL_KEY_LOW_HIGH;
        break;
    case CIL_DEFAULT_GLBLUB:
        range_str = NULL;
        break;
    }
    json_print_kv(indent, output, "default", "%s", default_str);
    json_print_next(output);
    json_print_kv(indent, output, "range", "%s", range_str);
}

/******************************************************************************
 *  File Labeling Statements                                                  *
 ******************************************************************************/

DEFINE_JSON_NODE(filecon, struct cil_filecon)
{
    json_print_kv(indent, output, "path", "%s", filecon->path_str);
    json_print_next(output);
    const char *file_type_str = NULL;
    switch (filecon->type) {
    case CIL_FILECON_FILE:
        file_type_str = CIL_KEY_FILE;
        break;
    case CIL_FILECON_DIR:
        file_type_str = CIL_KEY_DIR;
        break;
    case CIL_FILECON_CHAR:
        file_type_str = CIL_KEY_CHAR;
        break;
    case CIL_FILECON_BLOCK:
        file_type_str = CIL_KEY_BLOCK;
        break;
    case CIL_FILECON_SOCKET:
        file_type_str = CIL_KEY_SOCKET;
        break;
    case CIL_FILECON_PIPE:
        file_type_str = CIL_KEY_PIPE;
        break;
    case CIL_FILECON_SYMLINK:
        file_type_str = CIL_KEY_SYMLINK;
        break;
    case CIL_FILECON_ANY:
        file_type_str = CIL_KEY_ANY;
        break;
    default:
        assert(false /* unreachable */);
    }
    json_print_kv(indent, output, "fileType", "%s", file_type_str);
    json_print_next(output);
    json_print_kv(indent, output, "context", NULL);
    json_print_str_or_cil_data(indent, output, filecon->context_str, CIL_CONTEXT, filecon->context, cil_node->line);
}
DEFINE_JSON_NODE(fsuse, struct cil_fsuse)
{
    const char *fstype_str = NULL;
    switch (fsuse->type) {
    case CIL_FSUSE_TASK:
        fstype_str = CIL_KEY_TASK;
        break;
    case CIL_FSUSE_TRANS:
        fstype_str = CIL_KEY_TRANS;
        break;
    case CIL_FSUSE_XATTR:
        fstype_str = CIL_KEY_XATTR;
        break;
    default:
        assert(false /* unreachable */);
    }
    json_print_kv(indent, output, "fsType", "%s", fstype_str);
    json_print_next(output);
    json_print_kv(indent, output, "fsName", "%s", fsuse->fs_str);
    json_print_next(output);
    json_print_kv(indent, output, "context", NULL);
    json_print_str_or_cil_data(indent, output, fsuse->context_str, CIL_CONTEXT, fsuse->context, cil_node->line);
}
DEFINE_JSON_NODE(genfscon, struct cil_genfscon)
{
    json_print_kv(indent, output, "fsName", "%s", genfscon->fs_str);
    json_print_next(output);
    json_print_kv(indent, output, "path", "%s", genfscon->path_str);
    json_print_next(output);
    const char *file_type_str = NULL;
    switch (genfscon->file_type) {
    case CIL_FILECON_FILE:
        file_type_str = CIL_KEY_FILE;
        break;
    case CIL_FILECON_DIR:
        file_type_str = CIL_KEY_DIR;
        break;
    case CIL_FILECON_CHAR:
        file_type_str = CIL_KEY_CHAR;
        break;
    case CIL_FILECON_BLOCK:
        file_type_str = CIL_KEY_BLOCK;
        break;
    case CIL_FILECON_SOCKET:
        file_type_str = CIL_KEY_SOCKET;
        break;
    case CIL_FILECON_PIPE:
        file_type_str = CIL_KEY_PIPE;
        break;
    case CIL_FILECON_SYMLINK:
        file_type_str = CIL_KEY_SYMLINK;
        break;
    case CIL_FILECON_ANY:
        file_type_str = CIL_KEY_ANY;
        break;
    default:
        assert(false /* unreachable */);
    }
    json_print_kv(indent, output, "fileType", "%s", file_type_str);
    json_print_next(output);
    json_print_kv(indent, output, "context", NULL);
    json_print_str_or_cil_data(indent, output, genfscon->context_str, CIL_CONTEXT, genfscon->context, cil_node->line);
}

/******************************************************************************
 *  Infiniband Statements                                                     *
 ******************************************************************************/

DEFINE_JSON_NODE(ibpkeycon, struct cil_ibpkeycon)
{
    json_print_kv(indent, output, "subnet", "%s", ibpkeycon->subnet_prefix_str);
    json_print_next(output);
    json_print_kv(indent, output, "pkeyLow", "%" PRIu32, ibpkeycon->pkey_low);
    json_print_next(output);
    json_print_kv(indent, output, "pkeyHigh", "%" PRIu32, ibpkeycon->pkey_high);
    json_print_next(output);
    json_print_kv(indent, output, "context", NULL);
    json_print_str_or_cil_data(indent, output, ibpkeycon->context_str, CIL_CONTEXT, ibpkeycon->context, cil_node->line);
}
DEFINE_JSON_NODE(ibendportcon, struct cil_ibendportcon)
{
    json_print_kv(indent, output, "device", "%s", ibendportcon->dev_name_str);
    json_print_next(output);
    json_print_kv(indent, output, "port", "%" PRIu32, ibendportcon->port);
    json_print_next(output);
    json_print_kv(indent, output, "context", NULL);
    json_print_str_or_cil_data(indent, output, ibendportcon->context_str, CIL_CONTEXT, ibendportcon->context, cil_node->line);
}

/******************************************************************************
 *  Multi-Level Security Labeling Statements                                  *
 ******************************************************************************/

DEFINE_JSON_NODE_SIMPLE_DECL(sensitivity, struct cil_sens)
DEFINE_JSON_NODE_SIMPLE_DECL(sensitivityalias, struct cil_alias)
DEFINE_JSON_NODE_ALIAS_ACTUAL(sensitivityaliasactual, "sensitivity")
DEFINE_JSON_NODE_TYPE(sensitivityorder, struct cil_ordered)
{
    (void)cil_node;
    (void)sensitivityorder;
    return CIL_KEY_SENSITIVITYORDER;
}
DEFINE_JSON_NODE_SIMPLE_DECL(category, struct cil_cat)
DEFINE_JSON_NODE_SIMPLE_DECL(categoryalias, struct cil_alias)
DEFINE_JSON_NODE_ALIAS_ACTUAL(categoryaliasactual, "category")
DEFINE_JSON_NODE_TYPE(categoryorder, struct cil_ordered)
{
    (void)cil_node;
    (void)categoryorder;
    return CIL_KEY_CATORDER;
}
DEFINE_JSON_NODE(categoryset, struct cil_catset)
{
    (void)cil_node;
    json_print_kv(indent, output, "id", "%s", categoryset->datum.name);
    json_print_next(output);
    json_print_kv(indent, output, "category", NULL);
    json_print_expr(indent, output, categoryset->cats->str_expr);
}
DEFINE_JSON_NODE(sensitivitycategory, struct cil_senscat)
{
    (void)cil_node;
    json_print_kv(indent, output, "sensitivity", "%s", sensitivitycategory->sens_str);
    json_print_next(output);
    json_print_kv(indent, output, "category", NULL);
    json_print_expr(indent, output, sensitivitycategory->cats->str_expr);
}
DEFINE_JSON_NODE(level, struct cil_level)
{
    (void)cil_node;
    json_print_kv(indent, output, "id", "%s", level->datum.name);
    json_print_next(output);
    json_print_kv(indent, output, "sensitivity", "%s", level->sens_str);
    json_print_next(output);
    json_print_kv(indent, output, "category", NULL);
    if (level->cats) {
        json_print_expr(indent, output, level->cats->str_expr);
    } else {
        fputs("null", output);
    }
}
DEFINE_JSON_NODE(levelrange, struct cil_levelrange)
{
    json_print_kv(indent, output, "id", "%s", levelrange->datum.name);
    json_print_next(output);
    json_print_kv(indent, output, "low", NULL);
    json_print_str_or_cil_data(indent, output, levelrange->low_str, CIL_LEVEL, levelrange->low, cil_node->line);
    json_print_next(output);
    json_print_kv(indent, output, "high", NULL);
    json_print_str_or_cil_data(indent, output, levelrange->high_str, CIL_LEVEL, levelrange->high, cil_node->line);
}
DEFINE_JSON_NODE(rangetransition, struct cil_rangetransition)
{
    json_print_kv(indent, output, "source", "%s", rangetransition->src_str);
    json_print_next(output);
    json_print_kv(indent, output, "target", "%s", rangetransition->exec_str);
    json_print_next(output);
    json_print_kv(indent, output, "class", "%s", rangetransition->obj_str);
    json_print_next(output);
    json_print_kv(indent, output, "range", NULL);
    json_print_str_or_cil_data(indent, output, rangetransition->range_str, CIL_LEVELRANGE, rangetransition->range, cil_node->line);
}

/******************************************************************************
 *  Network Labeling Statements                                               *
 ******************************************************************************/

DEFINE_JSON_NODE(ipaddr, struct cil_ipaddr)
{
    (void)cil_node;
    json_print_kv(indent, output, "id", "%s", ipaddr->datum.name);
    json_print_next(output);
    char ip_str[40] = {'\0'};
    if (!inet_ntop(ipaddr->family, &ipaddr->ip, ip_str, sizeof(ip_str))) {
        error(EXIT_FAILURE, errno, "Failed to convert IP to string");
    }
    json_print_kv(indent, output, "ip", "%s", ip_str);
}
DEFINE_JSON_NODE(netifcon, struct cil_netifcon)
{
    json_print_kv(indent, output, "ifName", "%s", netifcon->interface_str);
    json_print_next(output);
    json_print_kv(indent, output, "ifContext", NULL);
    json_print_str_or_cil_data(indent, output, netifcon->if_context_str, CIL_CONTEXT, netifcon->if_context, cil_node->line);
    json_print_next(output);
    json_print_kv(indent, output, "packetContext", NULL);
    json_print_str_or_cil_data(indent, output, netifcon->packet_context_str, CIL_CONTEXT, netifcon->packet_context, cil_node->line);
}
DEFINE_JSON_NODE(nodecon, struct cil_nodecon)
{
    json_print_kv(indent, output, "subnet", NULL);
    json_print_str_or_cil_data(indent, output, nodecon->addr_str, CIL_IPADDR, nodecon->addr, cil_node->line);
    json_print_next(output);
    json_print_kv(indent, output, "mask", NULL);
    json_print_str_or_cil_data(indent, output, nodecon->mask_str, CIL_IPADDR, nodecon->mask, cil_node->line);
    json_print_next(output);
    json_print_kv(indent, output, "context", NULL);
    json_print_str_or_cil_data(indent, output, nodecon->context_str, CIL_CONTEXT, nodecon->context, cil_node->line);
}
DEFINE_JSON_NODE(portcon, struct cil_portcon)
{
    const char *proto_str = NULL;
    switch (portcon->proto) {
    case CIL_PROTOCOL_TCP:
        proto_str = CIL_KEY_TCP;
        break;
    case CIL_PROTOCOL_UDP:
        proto_str = CIL_KEY_UDP;
        break;
    case CIL_PROTOCOL_DCCP:
        proto_str = CIL_KEY_DCCP;
        break;
    case CIL_PROTOCOL_SCTP:
        proto_str = CIL_KEY_SCTP;
        break;
    default:
        assert(false /* unreachable */);
    }
    json_print_kv(indent, output, "protocol", "%s", proto_str);
    json_print_next(output);
    json_print_kv(indent, output, "portLow", "%" PRIu32, portcon->port_low);
    json_print_next(output);
    json_print_kv(indent, output, "portHigh", "%" PRIu32, portcon->port_high);
    json_print_next(output);
    json_print_kv(indent, output, "context", NULL);
    json_print_str_or_cil_data(indent, output, portcon->context_str, CIL_CONTEXT, portcon->context, cil_node->line);
}

/******************************************************************************
 *  Policy Configuration Statements                                           *
 ******************************************************************************/

DEFINE_JSON_NODE(mls, struct cil_mls)
{
    (void)cil_node;
    json_print_kv(indent, output, "value", "%b", mls->value);
}
DEFINE_JSON_NODE(handleunknown, struct cil_handleunknown)
{
    (void)cil_node;
    const char *action_str = NULL;
    switch (handleunknown->handle_unknown) {
    case SEPOL_ALLOW_UNKNOWN:
        action_str = CIL_KEY_HANDLEUNKNOWN_ALLOW;
        break;
    case SEPOL_DENY_UNKNOWN:
        action_str = CIL_KEY_HANDLEUNKNOWN_DENY;
        break;
    case SEPOL_REJECT_UNKNOWN:
        action_str = CIL_KEY_HANDLEUNKNOWN_REJECT;
        break;
    default:
        assert(false /* unreachable */);
    }
    json_print_kv(indent, output, "action", "%s", action_str);
}
DEFINE_JSON_NODE_SIMPLE_DECL(policycap, struct cil_policycap)

/******************************************************************************
 *  Role Statements                                                           *
 ******************************************************************************/

DEFINE_JSON_NODE_SIMPLE_DECL(role, struct cil_role)
DEFINE_JSON_NODE(roletype, struct cil_roletype)
{
    (void)cil_node;
    json_print_kv(indent, output, "role", "%s", roletype->role_str);
    json_print_next(output);
    json_print_kv(indent, output, "type", "%s", roletype->type_str);
}
DEFINE_JSON_NODE_SIMPLE_DECL(roleattribute, struct cil_roleattribute)
DEFINE_JSON_NODE(roleattributeset, struct cil_roleattributeset)
{
    (void)cil_node;
    json_print_kv(indent, output, "roleattribute", "%s", roleattributeset->attr_str);
    json_print_next(output);
    json_print_kv(indent, output, "roles", NULL);
    json_print_expr(indent, output, roleattributeset->str_expr);
}
DEFINE_JSON_NODE(roleallow, struct cil_roleallow)
{
    (void)cil_node;
    json_print_kv(indent, output, "source", "%s", roleallow->src_str);
    json_print_next(output);
    json_print_kv(indent, output, "target", "%s", roleallow->tgt_str);
}
DEFINE_JSON_NODE(roletransition, struct cil_roletransition)
{
    (void)cil_node;
    json_print_kv(indent, output, "source", "%s", roletransition->src_str);
    json_print_next(output);
    json_print_kv(indent, output, "target", "%s", roletransition->tgt_str);
    json_print_next(output);
    json_print_kv(indent, output, "class", "%s", roletransition->obj_str);
    json_print_next(output);
    json_print_kv(indent, output, "result", "%s", roletransition->result_str);
}
DEFINE_JSON_NODE_TYPE(rolebounds, struct cil_bounds)
{
    (void)rolebounds;
    (void)cil_node;
    return CIL_KEY_ROLEBOUNDS;
}

/******************************************************************************
 *  SID Statements                                                            *
 ******************************************************************************/

DEFINE_JSON_NODE_SIMPLE_DECL(sid, struct cil_sid)
DEFINE_JSON_NODE_TYPE(sidorder, struct cil_ordered)
{
    (void)sidorder;
    (void)cil_node;
    return CIL_KEY_SIDORDER;
}
DEFINE_JSON_NODE(sidcontext, struct cil_sidcontext)
{
    json_print_kv(indent, output, "sid", "%s", sidcontext->sid_str);
    json_print_next(output);
    json_print_kv(indent, output, "context", NULL);
    json_print_str_or_cil_data(indent, output, sidcontext->context_str, CIL_CONTEXT, sidcontext->context, cil_node->line);
}

/******************************************************************************
 *  Type Statements                                                           *
 ******************************************************************************/

DEFINE_JSON_NODE_SIMPLE_DECL(type, struct cil_type)
DEFINE_JSON_NODE_SIMPLE_DECL(typealias, struct cil_alias)
DEFINE_JSON_NODE_ALIAS_ACTUAL(typealiasactual, "type")
DEFINE_JSON_NODE_SIMPLE_DECL(typeattribute, struct cil_typeattribute)
DEFINE_JSON_NODE(typeattributeset, struct cil_typeattributeset)
{
    (void)cil_node;
    json_print_kv(indent, output, "typeattribute", "%s", typeattributeset->attr_str);
    json_print_next(output);
    json_print_kv(indent, output, "types", NULL);
    json_print_expr(indent, output, typeattributeset->str_expr);
}
DEFINE_JSON_NODE(expandtypeattribute, struct cil_expandtypeattribute)
{
    (void)cil_node;
    json_print_kv(indent, output, "types", NULL);
    indent = json_array_start(indent, output);
    for (const struct cil_list_item *item = expandtypeattribute->attr_strs->head; item; item = item->next) {
        assert(item->flavor == CIL_STRING);
        json_print_string(output, item->data);
        if (item->next) {
            json_print_next(output);
        }
    }
    indent = json_array_end(indent, output);
    json_print_next(output);
    json_print_kv(indent, output, "expand", "%b", expandtypeattribute->expand);
}
DEFINE_JSON_NODE_TYPE(typebounds, struct cil_bounds)
{
    (void)typebounds;
    (void)cil_node;
    return CIL_KEY_TYPEBOUNDS;
}
DEFINE_JSON_NODE(type_rule, struct cil_type_rule)
{
    (void)cil_node;
    json_print_kv(indent, output, "source", "%s", type_rule->src_str);
    json_print_next(output);
    json_print_kv(indent, output, "target", "%s", type_rule->tgt_str);
    json_print_next(output);
    json_print_kv(indent, output, "class", "%s", type_rule->obj_str);
    json_print_next(output);
    json_print_kv(indent, output, "result", "%s", type_rule->result_str);
}
DEFINE_JSON_NODE_TYPE(type_rule, struct cil_type_rule)
{
    (void)cil_node;
    switch (type_rule->rule_kind) {
    case CIL_TYPE_CHANGE:
        return CIL_KEY_TYPECHANGE;
    case CIL_TYPE_MEMBER:
        return CIL_KEY_TYPEMEMBER;
    case CIL_TYPE_TRANSITION:
        return CIL_KEY_TYPETRANSITION;
    default:
        assert(false /* unreachable */);
    }
}
DEFINE_JSON_NODE(nametypetransition, struct cil_nametypetransition)
{
    (void)cil_node;
    json_print_kv(indent, output, "source", "%s", nametypetransition->src_str);
    json_print_next(output);
    json_print_kv(indent, output, "target", "%s", nametypetransition->tgt_str);
    json_print_next(output);
    json_print_kv(indent, output, "class", "%s", nametypetransition->obj_str);
    json_print_next(output);
    json_print_kv(indent, output, "name", "%s", nametypetransition->name_str);
    json_print_next(output);
    json_print_kv(indent, output, "result", "%s", nametypetransition->result_str);
}
DEFINE_JSON_NODE_TYPE(nametypetransition, struct cil_nametypetransition)
{
    (void)nametypetransition;
    (void)cil_node;
    return CIL_KEY_TYPETRANSITION;
}
DEFINE_JSON_NODE(typepermissive, struct cil_typepermissive)
{
    (void)cil_node;
    json_print_kv(indent, output, "type", "%s", typepermissive->type_str);
}

/******************************************************************************
 *  User Statements                                                           *
 ******************************************************************************/

DEFINE_JSON_NODE_SIMPLE_DECL(user, struct cil_user)
DEFINE_JSON_NODE(userrole, struct cil_userrole)
{
    (void)cil_node;
    json_print_kv(indent, output, "user", "%s", userrole->user_str);
    json_print_next(output);
    json_print_kv(indent, output, "role", "%s", userrole->role_str);
}
DEFINE_JSON_NODE_SIMPLE_DECL(userattribute, struct cil_userattribute)
DEFINE_JSON_NODE(userattributeset, struct cil_userattributeset)
{
    (void)cil_node;
    json_print_kv(indent, output, "userattribute", "%s", userattributeset->attr_str);
    json_print_next(output);
    json_print_kv(indent, output, "users", NULL);
    json_print_expr(indent, output, userattributeset->str_expr);
}
DEFINE_JSON_NODE(userlevel, struct cil_userlevel)
{
    json_print_kv(indent, output, "user", "%s", userlevel->user_str);
    json_print_next(output);
    json_print_kv(indent, output, "level", NULL);
    json_print_str_or_cil_data(indent, output, userlevel->level_str, CIL_LEVEL, userlevel->level, cil_node->line);
}
DEFINE_JSON_NODE(userrange, struct cil_userrange)
{
    json_print_kv(indent, output, "user", "%s", userrange->user_str);
    json_print_next(output);
    json_print_kv(indent, output, "range", NULL);
    json_print_str_or_cil_data(indent, output, userrange->range_str, CIL_LEVELRANGE, userrange->range, cil_node->line);
}
DEFINE_JSON_NODE_TYPE(userbounds, struct cil_bounds)
{
    (void)userbounds;
    (void)cil_node;
    return CIL_KEY_USERBOUNDS;
}
DEFINE_JSON_NODE(userprefix, struct cil_userprefix)
{
    (void)cil_node;
    json_print_kv(indent, output, "user", "%s", userprefix->user_str);
    json_print_next(output);
    json_print_kv(indent, output, "prefix", "%s", userprefix->prefix_str);
}
DEFINE_JSON_NODE(selinuxuser, struct cil_selinuxuser)
{
    json_print_kv(indent, output, "name", "%s", selinuxuser->name_str);
    json_print_next(output);
    json_print_kv(indent, output, "user", "%s", selinuxuser->user_str);
    json_print_next(output);
    json_print_kv(indent, output, "range", NULL);
    json_print_str_or_cil_data(indent, output, selinuxuser->range_str, CIL_LEVELRANGE, selinuxuser->range, cil_node->line);
}
DEFINE_JSON_NODE(selinuxuserdefault, struct cil_selinuxuser)
{
    json_print_kv(indent, output, "user", "%s", selinuxuserdefault->user_str);
    json_print_next(output);
    json_print_kv(indent, output, "range", NULL);
    json_print_str_or_cil_data(indent, output, selinuxuserdefault->range_str, CIL_LEVELRANGE, selinuxuserdefault->range, cil_node->line);
}

/******************************************************************************
 *  Xen Statements                                                            *
 ******************************************************************************/

DEFINE_JSON_NODE(iomemcon, struct cil_iomemcon)
{
    json_print_kv(indent, output, "memAddrLow", "%" PRIu64, iomemcon->iomem_low);
    json_print_next(output);
    json_print_kv(indent, output, "memAddrHigh", "%" PRIu64, iomemcon->iomem_high);
    json_print_next(output);
    json_print_kv(indent, output, "context", NULL);
    json_print_str_or_cil_data(indent, output, iomemcon->context_str, CIL_CONTEXT, iomemcon->context, cil_node->line);
}
DEFINE_JSON_NODE(ioportcon, struct cil_ioportcon)
{
    json_print_kv(indent, output, "portLow", "%" PRIu32, ioportcon->ioport_low);
    json_print_next(output);
    json_print_kv(indent, output, "portHigh", "%" PRIu32, ioportcon->ioport_high);
    json_print_next(output);
    json_print_kv(indent, output, "context", NULL);
    json_print_str_or_cil_data(indent, output, ioportcon->context_str, CIL_CONTEXT, ioportcon->context, cil_node->line);
}
DEFINE_JSON_NODE(pcidevicecon, struct cil_pcidevicecon)
{
    json_print_kv(indent, output, "device", "%" PRIu32, pcidevicecon->dev);
    json_print_next(output);
    json_print_kv(indent, output, "context", NULL);
    json_print_str_or_cil_data(indent, output, pcidevicecon->context_str, CIL_CONTEXT, pcidevicecon->context, cil_node->line);
}
DEFINE_JSON_NODE(pirqcon, struct cil_pirqcon)
{
    json_print_kv(indent, output, "irq", "%" PRIu32, pirqcon->pirq);
    json_print_next(output);
    json_print_kv(indent, output, "context", NULL);
    json_print_str_or_cil_data(indent, output, pirqcon->context_str, CIL_CONTEXT, pirqcon->context, cil_node->line);
}
DEFINE_JSON_NODE(devicetreecon, struct cil_devicetreecon)
{
    json_print_kv(indent, output, "path", "%s", devicetreecon->path);
    json_print_next(output);
    json_print_kv(indent, output, "context", NULL);
    json_print_str_or_cil_data(indent, output, devicetreecon->context_str, CIL_CONTEXT, devicetreecon->context, cil_node->line);
}


static const struct json_cil_node_def cil_node_defs[] = {
    [CIL_ROOT] = { .type = "<root>" },
    /* Access Vector Statements */
    [CIL_AVRULE] = { REGISTER_JSON_NODE(avrule), REGISTER_JSON_NODE_TYPE(avrule) },
    [CIL_AVRULEX] = { REGISTER_JSON_NODE(avrule), REGISTER_JSON_NODE_TYPE(avrulex) },
    [CIL_DENY_RULE] = { REGISTER_JSON_NODE(deny) },
    /* Call / Macro Statements */
    [CIL_CALL] = { REGISTER_JSON_NODE(call) },
    [CIL_MACRO] = { REGISTER_JSON_NODE(macro) },
    /* Class and Permission Statements */
    [CIL_CLASSPERMS] = { REGISTER_JSON_NODE(classperms) },
    [CIL_COMMON] = { REGISTER_JSON_NODE(class), REGISTER_JSON_NODE_TYPE(common) },
    [CIL_CLASSCOMMON] = { REGISTER_JSON_NODE(classcommon) },
    [CIL_CLASS] = { REGISTER_JSON_NODE(class) },
    [CIL_CLASSORDER] = { REGISTER_JSON_NODE(ordered), REGISTER_JSON_NODE_TYPE(classorder) },
    [CIL_CLASSPERMISSION] = { REGISTER_JSON_NODE(classpermission) },
    [CIL_CLASSPERMISSIONSET] = { REGISTER_JSON_NODE(classpermissionset) },
    [CIL_MAP_CLASS] = { REGISTER_JSON_NODE(classmap) },
    [CIL_CLASSMAPPING] = { REGISTER_JSON_NODE(classmapping) },
    [CIL_PERMISSIONX] = { REGISTER_JSON_NODE(permissionx) },
    /* Conditional Statements */
    [CIL_BOOL] = { REGISTER_JSON_NODE(boolean) },
    [CIL_BOOLEANIF] = { REGISTER_JSON_NODE(booleanif) },
    [CIL_TUNABLE] = { REGISTER_JSON_NODE(tunable) },
    [CIL_TUNABLEIF] = { REGISTER_JSON_NODE(tunableif) },
    /* Constraint Statements */
    [CIL_CONSTRAIN] = { REGISTER_JSON_NODE(constrain) },
    [CIL_VALIDATETRANS] = { REGISTER_JSON_NODE(validatetrans) },
    [CIL_MLSCONSTRAIN] = { REGISTER_JSON_NODE(constrain), REGISTER_JSON_NODE_TYPE(mlsconstrain) },
    [CIL_MLSVALIDATETRANS] = { REGISTER_JSON_NODE(validatetrans), REGISTER_JSON_NODE_TYPE(mlsvalidatetrans) },
    /* Container Statements */
    [CIL_BLOCK] = { REGISTER_JSON_NODE(block) },
    [CIL_BLOCKABSTRACT] = { REGISTER_JSON_NODE(blockabstract) },
    [CIL_BLOCKINHERIT] = { REGISTER_JSON_NODE(blockinherit) },
    [CIL_OPTIONAL] = { REGISTER_JSON_NODE(optional) },
    [CIL_IN] = { REGISTER_JSON_NODE(in) },
    /* Context Statement */
    [CIL_CONTEXT] = { REGISTER_JSON_NODE(context) },
    /* Default Object Statements */
    [CIL_DEFAULTUSER] = { REGISTER_JSON_NODE(cil_default), REGISTER_JSON_NODE_TYPE(cil_default) },
    [CIL_DEFAULTROLE] = { REGISTER_JSON_NODE(cil_default), REGISTER_JSON_NODE_TYPE(cil_default) },
    [CIL_DEFAULTTYPE] = { REGISTER_JSON_NODE(cil_default), REGISTER_JSON_NODE_TYPE(cil_default) },
    [CIL_DEFAULTRANGE] = { REGISTER_JSON_NODE(defaultrange) },
    /* File Labeling Statements */
    [CIL_FILECON] = { REGISTER_JSON_NODE(filecon) },
    [CIL_FSUSE] = { REGISTER_JSON_NODE(fsuse) },
    [CIL_GENFSCON] = { REGISTER_JSON_NODE(genfscon) },
    /* Infiniband Statements */
    [CIL_IBPKEYCON] = { REGISTER_JSON_NODE(ibpkeycon) },
    [CIL_IBENDPORTCON] = { REGISTER_JSON_NODE(ibendportcon) },
    /* Multi-Level Security Labeling Statements */
    [CIL_SENS] = { REGISTER_JSON_NODE(sensitivity) },
    [CIL_SENSALIAS] = { REGISTER_JSON_NODE(sensitivityalias) },
    [CIL_SENSALIASACTUAL] = { REGISTER_JSON_NODE(sensitivityaliasactual) },
    [CIL_SENSITIVITYORDER] = { REGISTER_JSON_NODE(ordered), REGISTER_JSON_NODE_TYPE(sensitivityorder) },
    [CIL_CAT] = { REGISTER_JSON_NODE(category) },
    [CIL_CATALIAS] = { REGISTER_JSON_NODE(categoryalias) },
    [CIL_CATALIASACTUAL] = { REGISTER_JSON_NODE(categoryaliasactual) },
    [CIL_CATORDER] = { REGISTER_JSON_NODE(ordered), REGISTER_JSON_NODE_TYPE(categoryorder) },
    [CIL_CATSET] = { REGISTER_JSON_NODE(categoryset) },
    [CIL_SENSCAT] = { REGISTER_JSON_NODE(sensitivitycategory) },
    [CIL_LEVEL] = { REGISTER_JSON_NODE(level) },
    [CIL_LEVELRANGE] = { REGISTER_JSON_NODE(levelrange) },
    [CIL_RANGETRANSITION] = { REGISTER_JSON_NODE(rangetransition) },
    /* Network Labeling Statements */
    [CIL_IPADDR] = { REGISTER_JSON_NODE(ipaddr) },
    [CIL_NETIFCON] = { REGISTER_JSON_NODE(netifcon) },
    [CIL_NODECON] = { REGISTER_JSON_NODE(nodecon) },
    [CIL_PORTCON] = { REGISTER_JSON_NODE(portcon) },
    // /* Policy Configuration Statements */
    [CIL_MLS] = { REGISTER_JSON_NODE(mls) },
    [CIL_HANDLEUNKNOWN] = { REGISTER_JSON_NODE(handleunknown) },
    [CIL_POLICYCAP] = { REGISTER_JSON_NODE(policycap) },
    // /* Role Statements */
    [CIL_ROLE] = { REGISTER_JSON_NODE(role) },
    [CIL_ROLETYPE] = { REGISTER_JSON_NODE(roletype) },
    [CIL_ROLEATTRIBUTE] = { REGISTER_JSON_NODE(roleattribute) },
    [CIL_ROLEATTRIBUTESET] = { REGISTER_JSON_NODE(roleattributeset) },
    [CIL_ROLEALLOW] = { REGISTER_JSON_NODE(roleallow) },
    [CIL_ROLETRANSITION] = { REGISTER_JSON_NODE(roletransition) },
    [CIL_ROLEBOUNDS] = { REGISTER_JSON_NODE(bounds), REGISTER_JSON_NODE_TYPE(rolebounds) },
    // /* SID Statements */
    [CIL_SID] = { REGISTER_JSON_NODE(sid) },
    [CIL_SIDORDER] = { REGISTER_JSON_NODE(ordered), REGISTER_JSON_NODE_TYPE(sidorder) },
    [CIL_SIDCONTEXT] = { REGISTER_JSON_NODE(sidcontext) },
    // /* Type Statements */
    [CIL_TYPE] = { REGISTER_JSON_NODE(type) },
    [CIL_TYPEALIAS] = { REGISTER_JSON_NODE(typealias) },
    [CIL_TYPEALIASACTUAL] = { REGISTER_JSON_NODE(typealiasactual) },
    [CIL_TYPEATTRIBUTE] = { REGISTER_JSON_NODE(typeattribute) },
    [CIL_TYPEATTRIBUTESET] = { REGISTER_JSON_NODE(typeattributeset) },
    [CIL_EXPANDTYPEATTRIBUTE] = { REGISTER_JSON_NODE(expandtypeattribute) },
    [CIL_TYPEBOUNDS] = { REGISTER_JSON_NODE(bounds), REGISTER_JSON_NODE_TYPE(typebounds) },
    [CIL_TYPE_RULE] = { REGISTER_JSON_NODE(type_rule), REGISTER_JSON_NODE_TYPE(type_rule) },
    [CIL_NAMETYPETRANSITION] = { REGISTER_JSON_NODE(nametypetransition), REGISTER_JSON_NODE_TYPE(nametypetransition) },
    [CIL_TYPEPERMISSIVE] = { REGISTER_JSON_NODE(typepermissive) },
    // /* User Statements */
    [CIL_USER] = { REGISTER_JSON_NODE(user) },
    [CIL_USERROLE] = { REGISTER_JSON_NODE(userrole) },
    [CIL_USERATTRIBUTE] = { REGISTER_JSON_NODE(userattribute) },
    [CIL_USERATTRIBUTESET] = { REGISTER_JSON_NODE(userattributeset) },
    [CIL_USERLEVEL] = { REGISTER_JSON_NODE(userlevel) },
    [CIL_USERRANGE] = { REGISTER_JSON_NODE(userrange) },
    [CIL_USERBOUNDS] = { REGISTER_JSON_NODE(bounds), REGISTER_JSON_NODE_TYPE(userbounds) },
    [CIL_USERPREFIX] = { REGISTER_JSON_NODE(userprefix) },
    [CIL_SELINUXUSER] = { REGISTER_JSON_NODE(selinuxuser) },
    [CIL_SELINUXUSERDEFAULT] = { REGISTER_JSON_NODE(selinuxuserdefault) },
    // /* Xen Statements */
    [CIL_IOMEMCON] = { REGISTER_JSON_NODE(iomemcon) },
    [CIL_IOPORTCON] = { REGISTER_JSON_NODE(ioportcon) },
    [CIL_PCIDEVICECON] = { REGISTER_JSON_NODE(pcidevicecon) },
    [CIL_PIRQCON] = { REGISTER_JSON_NODE(pirqcon) },
    [CIL_DEVICETREECON] = { REGISTER_JSON_NODE(devicetreecon) },
};
#define CIL_NODE_DEFS_COUNT (sizeof(cil_node_defs) / sizeof(*cil_node_defs))

static void json_print_hash(FILE *output, const char hash[HASH_SIZE])
{
    fputc('"', output);
    for (size_t i = 0; i < HASH_SIZE; i++) {
        fprintf(output, "%02hhx", (unsigned char)hash[i]);
    }
    fputc('"', output);
}

static void json_print_cil_node_info(int indent, FILE *output, struct cil_tree_node *cil_node)
{
    if (cil_node->flavor >= CIL_NODE_DEFS_COUNT || !cil_node_defs[cil_node->flavor].type) {
        error(EXIT_FAILURE, 0, "json_print_cil_node_info: Unknown node type encountered: %d", cil_node->flavor);
    }
    const struct json_cil_node_def *def = &cil_node_defs[cil_node->flavor];

    json_print_kv(indent, output, "flavor", "%s", def->type_fn ? def->type_fn(cil_node) : def->type);
    json_print_next(output);
    json_print_kv(indent, output, "line", "%" PRIu32, cil_node->line);
}

static void json_print_cil_node(int indent, FILE *output, struct cil_tree_node *cil_node)
{
    if (cil_node->flavor >= CIL_NODE_DEFS_COUNT || !cil_node_defs[cil_node->flavor].type) {
        error(EXIT_FAILURE, 0, "json_print_cil_node_info: Unknown node type encountered: %d", cil_node->flavor);
    }
    const struct json_cil_node_def *def = &cil_node_defs[cil_node->flavor];

    indent = json_object_start(indent, output);

    json_print_cil_node_info(indent, output, cil_node);
    if (def->print_fn) {
        json_print_next(output);
        def->print_fn(indent, output, cil_node);
    }

    indent = json_object_end(indent, output);
}

static void json_print_diff(int indent, FILE *output, const struct diff *diff)
{
    indent = json_object_start(indent, output);

    const char *side_str = NULL;
    switch (diff->side) {
    case DIFF_LEFT:
        side_str = "LEFT";
        break;
    case DIFF_RIGHT:
        side_str = "RIGHT";
        break;
    default:
        assert(false /* Unreachable */);
    }
    json_print_kv(indent, output, "side", "%s", side_str);
    json_print_next(output);
    json_print_kv(indent, output, "hash", NULL);
    json_print_hash(output, diff->node->full_hash);
    json_print_next(output);
    json_print_kv(indent, output, "description", "%s", diff->decription);
    json_print_next(output);
    json_print_kv(indent, output, "node", NULL);
    json_print_cil_node(indent, output, diff->node->cil_node);

    indent = json_object_end(indent, output);
}

static void json_print_diff_context(const struct cmp_node *node, int indent, FILE *output)
{
    indent = json_object_start(indent, output);

    json_print_cil_node_info(indent, output, node->cil_node);
    json_print_next(output);
    json_print_kv(indent, output, "hash", NULL);
    json_print_hash(output, node->full_hash);

    indent = json_object_end(indent, output);
}

static void json_print_diff_tree_node(const struct diff_tree_node *diff_node, int indent, FILE *output)
{
    indent = json_object_start(indent, output);

    json_print_kv(indent, output, "left", NULL);
    json_print_diff_context(diff_node->left_node, indent, output);
    json_print_next(output);
    json_print_kv(indent, output, "right", NULL);
    json_print_diff_context(diff_node->right_node, indent, output);
    json_print_next(output);

    json_print_kv(indent, output, "diffs", NULL);
    indent = json_array_start(indent, output);
    for (const struct diff *diff = diff_node->dl_head; diff; diff = diff->next) {
        json_print_indent(indent, output);
        json_print_diff(indent, output, diff);
        if (diff->next) {
            json_print_next(output);
        }
    }
    indent = json_array_end(indent, output);
    json_print_next(output);

    json_print_kv(indent, output, "children", NULL);
    indent = json_array_start(indent, output);
    for (const struct diff_tree_node *child = diff_node->cl_head; child; child = child->next) {
        json_print_indent(indent, output);
        json_print_diff_tree_node(child, indent, output);
        if (child->next) {
            fputc(',', output);
        }
    }
    indent = json_array_end(indent, output);

    indent = json_object_end(indent, output);
}

void json_print_diff_tree(const struct diff_tree_node *root, bool pretty, FILE *output)
{
    json_print_diff_tree_node(root, pretty ? 0 : -1, output);
    fputc('\n', output);
}
