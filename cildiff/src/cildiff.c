#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

#include <error.h>

#include <bzlib.h>

#include <sepol/errcodes.h>
#include <cil/cil.h>
#include <cil_build_ast.h>
#include <cil_internal.h>

#include "cil_file.h"
#include "cil_node.h"
#include "cmp_common.h"
#include "cmp_node.h"
#include "diff.h"
#include "options.h"


int load_cil_file(cil_db_t *cil_db, const char *file_path)
{
    int rc = -1;
    struct cil_file cil_file;

    if (cil_file_read(file_path, &cil_file))
        goto exit;
    if (cil_add_file(cil_db, file_path, cil_file.data, cil_file.data_len) != SEPOL_OK)
        goto exit;
    if (cil_build_ast(cil_db, cil_db->parse->root, cil_db->ast->root) != SEPOL_OK) {
        error(0,0, "Failed to build CIL AST of '%s'", file_path);
        goto exit;
    }
    rc = 0;

exit:
    cil_file_destroy(&cil_file);
    return rc;
}

int main(int argc, char *argv[])
{
    int rc = EXIT_FAILURE;

    struct options cli_options = {0};
    if (parse_options(argc, argv, &cli_options))
        goto exit;

    cil_db_t *left_db;
    cil_db_init(&left_db);
    cil_db_t *right_db;
    cil_db_init(&right_db);

    if (load_cil_file(left_db, cli_options.left_path))
        goto free_cil_db;
    if (load_cil_file(right_db, cli_options.right_path))
        goto free_cil_db;

    struct cmp_node *left_root = cmp_node_create(cil_node_from_tree_node(left_db->ast->root));
    struct cmp_node *right_root = cmp_node_create(cil_node_from_tree_node(right_db->ast->root));
    printf("; Left hash: ");
    for (size_t i = 0; i < HASH_SIZE; i++) {
        printf("%02hhx", left_root->full_hash[i]);
    }
    putchar('\n');
    printf("; Right hash: ");
    for (size_t i = 0; i < HASH_SIZE; i++) {
        printf("%02hhx", right_root->full_hash[i]);
    }
    putchar('\n');

    struct diff_tree_node *diff_root = diff_tree_create(left_root->cil_node, right_root->cil_node);
    cmp_node_compare(left_root, right_root, diff_root);
    diff_tree_print(diff_root, stdout);

    diff_tree_destroy(diff_root);
    cmp_node_destroy(left_root);
    cmp_node_destroy(right_root);
    rc = EXIT_SUCCESS;

free_cil_db:
    cil_db_destroy(&right_db);
    cil_db_destroy(&left_db);
exit:
    return rc;
}
