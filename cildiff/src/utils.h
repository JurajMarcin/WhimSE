#ifndef UTILS_H
#define UTILS_H

#include <cil/cil.h>

#define MAYBE(s, a) ((s) ? ((s)->a) : NULL)

#define EITHER(s1, s2, a) ((s1) ? ((s1)->a) : ((s2)->a))

#define UNUSED(sym) ((void)(sym))

struct file_data {
    const char *path;
    size_t len;
    char *data;
};

int file_read(const char *path, struct file_data *data);

void file_data_destroy(struct file_data *data);

#endif
