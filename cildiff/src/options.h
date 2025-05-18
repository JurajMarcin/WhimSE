#ifndef CLI_OPTIONS_H
#define CLI_OPTIONS_H

#include <stdbool.h>

struct options {
    bool json;
    bool json_pretty;
    const char *left_path;
    const char *right_path;
};

int parse_options(int argc, char *argv[], struct options *cli_options);

#endif
