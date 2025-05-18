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

#include "mem.h"

#include <errno.h>
#include <error.h>
#include <string.h>

inline void __mem_check(void *mem, const char *verb, const char *file, int line)
{
    if (!mem) {
        error(EXIT_FAILURE, errno, "Failed to %s memory at %s:%d", verb, file,
              line);
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

inline void *__mem_realloc(void *old_mem, size_t new_size, const char *file,
                           int line)
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
