#include "utils.h"
#include "mem.h"

#include <error.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <bzlib.h>

#define BZ2_MAGICSTR "BZh"
#define BZ2_MAGICLEN (sizeof(BZ2_MAGICSTR) - 1)

static int read_compressed_file(size_t file_start_len,
                                char file_start[file_start_len], FILE *file,
                                struct file_data *data)
{
    int bzerror;
    BZFILE *bz_file =
        BZ2_bzReadOpen(&bzerror, file, 0, 0, file_start, file_start_len);
    if (bzerror != BZ_OK) {
        error(0, errno, "Failed to decompress file '%s'", data->path);
        goto exit;
    }

    do {
        char buffer[4096];
        int n_read = BZ2_bzRead(&bzerror, bz_file, buffer, sizeof(buffer));
        size_t new_len = data->len + n_read;
        data->data = mem_realloc(data->data, new_len * sizeof(*data->data));
        memcpy(&data->data[data->len], buffer, n_read);
        data->len = new_len;
    } while (bzerror == BZ_OK);
    if (bzerror != BZ_STREAM_END) {
        error(0, errno, "Failed to decompress file '%s'", data->path);
        goto close_bz_file;
    }

close_bz_file:
    BZ2_bzReadClose(&bzerror, bz_file);
exit:
    return bzerror == BZ_OK ? 0 : -1;
}

static int read_text_file(FILE *file, struct file_data *data)
{
    char buffer[4096];
    size_t n_read;
    while ((n_read = fread(buffer, 1, sizeof(buffer), file)) > 0) {
        size_t new_len = data->len + n_read;
        data->data = mem_realloc(data->data, new_len * sizeof(*data->data));
        memcpy(&data->data[data->len], buffer, n_read);
        data->len = new_len;
    }
    if (ferror(file)) {
        error(0, errno, "Failed to read file '%s'", data->path);
        return -1;
    }

    return 0;
}

int file_read(const char *path, struct file_data *data)
{
    int rc = -1;
    struct file_data tmp_data = {
        .path = path,
    };
    FILE *file;
    if (strcmp(path, "-") == 0) {
        file = stdin;
        tmp_data.path = "<stdin>";
    } else {
        file = fopen(path, "r");
        if (!file) {
            error(0, errno, "Failed open file '%s'", path);
            goto exit;
        }
    }

    char magic[BZ2_MAGICLEN];
    size_t magic_len = fread(magic, sizeof(*magic), BZ2_MAGICLEN, file);
    bool is_compressed =
        magic_len == BZ2_MAGICLEN && !memcmp(magic, BZ2_MAGICSTR, BZ2_MAGICLEN);

    if (ferror(file)) {
        error(0, errno, "Failed to read file '%s'", path);
        goto close_file;
    }

    if (is_compressed) {
        rc = read_compressed_file(sizeof(magic), magic, file, &tmp_data);
    } else {
        tmp_data.len = magic_len;
        tmp_data.data = mem_dup(magic, magic_len);
        rc = read_text_file(file, &tmp_data);
    }
    *data = tmp_data;

close_file:
    fclose(file);
exit:
    return rc;
}

void file_data_destroy(struct file_data *data)
{
    free(data->data);
    memset(data, 0, sizeof(*data));
}
