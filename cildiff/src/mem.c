#include "mem.h"

#include <errno.h>
#include <error.h>
#include <string.h>


inline void __mem_check(void *mem, const char *verb, const char *file, int line)
{
    if (!mem) {
        error(EXIT_FAILURE, errno, "Failed to %s memory at %s:%d", verb, file, line);
    }
}

inline void *__mem_alloc(size_t size, const char *file, int line)
{
    if (size == 0) {
        return NULL;
    }
    void *mem = malloc(size);
    __mem_check(mem, "allocate", file, line);
    return mem;
}

inline void *__mem_realloc(void *old_mem, size_t new_size, const char *file, int line)
{
    if (new_size == 0) {
        free(old_mem);
        return NULL;
    }
    void *new_mem = realloc(old_mem, new_size);
    __mem_check(new_mem, "reallocate", file, line);
    return new_mem;
}

inline void *__mem_dup(void *mem, size_t size, const char *file, int line)
{
    void *dup_mem = __mem_alloc(size, file, line);
    memcpy(dup_mem, mem, size);
    return dup_mem;
}
