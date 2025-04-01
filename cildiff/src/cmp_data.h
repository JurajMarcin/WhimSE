#ifndef CMP_DATA_H
#define CMP_DATA_H

#include <cil_internal.h>
#include <cil_flavor.h>

#include "cmp_common.h"


struct cmp_data {
    enum cil_flavor flavor;
    const void *cil_data;
    char partial_hash[HASH_SIZE];
    char full_hash[HASH_SIZE];
};

void cmp_data_init(enum cil_flavor flavor, const void *cil_data, struct cmp_data *cmp_data);

#endif
