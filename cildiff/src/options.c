#include "options.h"

#include <stdio.h>

static void print_usage(const char *progname)
{
    printf("Usage: %s LEFT RIGHT\n", progname);
}

int parse_options(int argc, char *argv[], struct options *cli_options)
{
    if (argc < 3) {
        print_usage(argv[0]);
        return -1;
    }
    *cli_options = (struct options) {
        .left_path = argv[1],
        .right_path = argv[2],
    };

    return 0;
}
