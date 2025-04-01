#include "cil_file.h"

#include <error.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <bzlib.h>


#define BZ2_MAGICSTR "BZh"
#define BZ2_MAGICLEN (sizeof(BZ2_MAGICSTR)-1)


static int read_compressed_file(size_t file_start_len,
                                char file_start[file_start_len], FILE *file,
                                struct cil_file *cil_file)
{
    int bzerror;
    BZFILE *bz_file = BZ2_bzReadOpen(&bzerror, file, 0, 0, file_start,
                                     file_start_len);
    if (bzerror != BZ_OK) {
        error(0, errno, "Failed to decompress file '%s'", cil_file->path);
        goto exit;
    }

    do {
        char buffer[4096];
        int n_read = BZ2_bzRead(&bzerror, bz_file, buffer, sizeof(buffer));
        size_t tmp_len = cil_file->data_len + n_read;
        char *tmp = realloc(cil_file->data, tmp_len);
        if (!tmp) {
            error(0, errno, "Not enough memory");
            goto close_bz_file;
        }
        cil_file->data = tmp;
        memcpy(&cil_file->data[cil_file->data_len], buffer, n_read);
        cil_file->data_len = tmp_len;
    } while (bzerror == BZ_OK);
    if (bzerror != BZ_STREAM_END) {
        error(0, errno, "Failed to decompress file '%s'", cil_file->path);
        goto close_bz_file;
    }

close_bz_file:
    BZ2_bzReadClose(&bzerror, bz_file);
exit:
    return bzerror == BZ_OK ? 0 : -1;
}

static int read_text_file(FILE *file, struct cil_file *cil_file)
{
    char buffer[4096];
    size_t n_read;
    while ((n_read = fread(buffer, 1, sizeof(buffer), file)) > 0) {
        size_t tmp_len = cil_file->data_len + n_read;
        char *tmp = realloc(cil_file->data, tmp_len * sizeof(char));
        if (!tmp) {
            error(0, errno, "Not enough memory");
            return -1;
        }
        cil_file->data = tmp;
        memcpy(&cil_file->data[cil_file->data_len], buffer, n_read);
        cil_file->data_len = tmp_len;
    }
    if (ferror(file)) {
        error(0, errno, "Failed to read file '%s'", cil_file->path);
        return -1;
    }

    return 0;
}


int cil_file_read(const char *path, struct cil_file *cil_file)
{
    int rc = -1;
    struct cil_file tmp_cil_file = {
        .path = path,
    };
    FILE *file;
    if (strcmp(path, "-") == 0) {
        file = stdin;
        tmp_cil_file.path = "<stdin>";
    } else {
        file = fopen(path, "r");
        if (!file) {
            error(0, errno, "Cannot open file '%s'", path);
            goto exit;
        }
    }

    char magic[BZ2_MAGICLEN];
    size_t magic_len = fread(magic, sizeof(char), BZ2_MAGICLEN, file);
    bool is_compressed = magic_len == BZ2_MAGICLEN &&
        !memcmp(magic, BZ2_MAGICSTR, BZ2_MAGICLEN);

    if (ferror(file)) {
        error(0, errno, "Error with file '%s'", path);
        goto close_file;
    }

    if (is_compressed) {
        rc = read_compressed_file(sizeof(magic), magic, file,
                                  &tmp_cil_file);
    } else {
        tmp_cil_file.data_len = magic_len;
        tmp_cil_file.data = malloc(magic_len);
        if (!tmp_cil_file.data) {
            error(0, errno, "Not enough memory");
            goto close_file;
        }
        memcpy(tmp_cil_file.data, magic, magic_len);
        rc = read_text_file(file, &tmp_cil_file);
    }
    *cil_file = tmp_cil_file;

close_file:
    fclose(file);
exit:
    return rc;
}

void cil_file_destroy(struct cil_file *cil_file)
{
    if (!cil_file) {
        return;
    }
    free(cil_file->data);
    cil_file->data = NULL;
    cil_file->data_len = 0;
}
