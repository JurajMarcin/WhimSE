#ifndef CILFILE_H
#define CILFILE_H

#include <cil/cil.h>

struct cil_file {
    const char *path;
    size_t data_len;
    char *data;
};

int cil_file_read(const char *path, struct cil_file *cil_file);

void cil_file_destroy(struct cil_file *cil_file);

#endif // !CILFILE_H
