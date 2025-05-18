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

#include <error.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

#include <sepol/errcodes.h>
#include <cil/cil.h>
#include <cil_build_ast.h>
#include <cil_internal.h>

#include "cmp_common.h"
#include "cmp_node.h"
#include "diff.h"
#include "json.h"
#include "options.h"
#include "utils.h"


int load_cil_file(cil_db_t *cil_db, const char *file_path)
{
    int rc = -1;
    struct file_data data = {0};

    if (file_read(file_path, &data))
        goto exit;
    if (cil_add_file(cil_db, file_path, data.data, data.len) != SEPOL_OK)
        goto exit;
    if (cil_build_ast(cil_db, cil_db->parse->root, cil_db->ast->root) != SEPOL_OK) {
        error(0,0, "Failed to build CIL AST of '%s'", file_path);
        goto exit;
    }
    rc = 0;

exit:
    file_data_destroy(&data);
    return rc;
}

int main(int argc, char *argv[])
{
    int exit_status = EXIT_FAILURE;

    struct options options = {0};
    int rc = parse_options(argc, argv, &options);
    if (rc) {
        if (rc > 0)
            exit_status = EXIT_SUCCESS;
        goto exit;
    }

    cil_db_t *left_db;
    cil_db_init(&left_db);
    cil_db_t *right_db;
    cil_db_init(&right_db);

    if (load_cil_file(left_db, options.left_path))
        goto free_cil_db;
    if (load_cil_file(right_db, options.right_path))
        goto free_cil_db;

    struct cmp_node *left_root = cmp_node_create(left_db->ast->root);
    struct cmp_node *right_root = cmp_node_create(right_db->ast->root);
    if (!options.json) {
        char hash_string[HASH_SIZE * 2 + 1];
        cmp_hash_to_string(left_root->full_hash, hash_string);
        printf("; Left hash: %s\n", hash_string);
        cmp_hash_to_string(right_root->full_hash, hash_string);
        printf("; Right hash: %s\n", hash_string);
    }

    struct diff_tree_node *diff_root = diff_tree_create(left_root, right_root);
    cmp_node_compare(left_root, right_root, diff_root);
    if (options.json) {
        json_print_diff_tree(diff_root, options.json_pretty, stdout);
    } else {
        diff_tree_print(diff_root, stdout);
    }

    diff_tree_destroy(diff_root);
    cmp_node_destroy(left_root);
    cmp_node_destroy(right_root);
    exit_status = EXIT_SUCCESS;

free_cil_db:
    cil_db_destroy(&right_db);
    cil_db_destroy(&left_db);
exit:
    return exit_status;
}
