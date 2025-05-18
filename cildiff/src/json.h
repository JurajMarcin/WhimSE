#ifndef CILDIFF_JSON_H
#define CILDIFF_JSON_H

#include <stdbool.h>
#include <stdio.h>

#include "diff.h"

void json_print_diff_tree(const struct diff_tree_node *diff_node, bool pretty,
                          FILE *output);

#endif
