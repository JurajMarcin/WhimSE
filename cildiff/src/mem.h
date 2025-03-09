#ifndef MEM_H
#define MEM_H

#include <stddef.h>
#include <stdlib.h>


void *__mem_alloc(size_t size, const char *file, int line);
#define mem_alloc(size) __mem_alloc(size, __FILE__, __LINE__)

void *__mem_realloc(void *old_mem, size_t new_size, const char *file, int line);
#define mem_realloc(old_mem, new_size) __mem_realloc(old_mem, new_size, __FILE__, __LINE__)

#define mem_free(mem) do { free(mem); (mem) = NULL; } while (0)

void __mem_check(void *mem, const char *verb, const char *file, int line);
#define mem_check(mem) __mem_check(mem, "allocate", __FILE__, __LINE__);

void *__mem_dup(void *mem, size_t size, const char *file, int line);
#define mem_dup(mem, size) __mem_dup(mem, size, __FILE__, __LINE__)

#endif
