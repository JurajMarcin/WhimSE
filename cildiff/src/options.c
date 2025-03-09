#include "options.h"

#include <error.h>
#include <getopt.h>
#include <stdio.h>
#include <string.h>


static void print_usage(const char *progname)
{
    printf("Usage: %s LEFT RIGHT\n", progname);
}

static void print_help(const char *progname)
{
    printf("NAME\n"
           "    cildiff - compute difference between two SELinux CIL policy files\n"\
           "\n"
           "SYNOPSIS\n"
           "    %s [OPTIONS] LEFT RIGHT\n"
           "\n"
           "OPTIONS\n"
           "    --json[=pretty]\n"
           "        format output in JSON instead of CIL with plain text comments,\n"
           "        optionally with pretty formatting\n"
           "\n"
           "ARGUMENTS\n"
           "    LEFT RIGHT\n"
           "        CIL files to compare, if either is '-', standard input is read instead.\n"
           "        The file can be either plain text or compressed with BZ2.\n", progname);
}

static const struct option opts[] = {
    { "help", no_argument, NULL, 'h' },
    { "json", optional_argument, NULL, 'j' },
    { NULL, 0, NULL, 0},
};

int parse_options(int argc, char *argv[], struct options *options)
{
    struct options tmp_options = {0};
    int opt;
    while ((opt = getopt_long(argc, argv, "h", opts, NULL)) != -1) {
        switch (opt) {
        case 'h':
            print_help(argv[0]);
            return 1;
        case 'j':
            tmp_options.json = true;
            if (optarg && !strcmp(optarg, "pretty")) {
                tmp_options.json_pretty = true;
            }
            break;
        default:
            error(0, 0, "Invalid option, run '%s -h' for help", argv[0]);
            return -1;
        }
    }
    if (argc - optind < 2) {
        print_usage(argv[0]);
        return -1;
    }
    tmp_options.left_path = argv[optind];
    tmp_options.right_path = argv[optind + 1];

    *options = tmp_options;

    return 0;
}
