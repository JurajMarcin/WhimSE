#ifndef CMP_COMMON_H
#define CMP_COMMON_H

#include <stddef.h>

#include <sepol/policydb/hashtab.h>


#define HASH_SIZE 32


void cmp_hash(size_t data_len, const void *data, char hash[HASH_SIZE]);


struct cmp_hash_state;

struct cmp_hash_state *cmp_hash_begin(const char *flavor);

void cmp_hash_update(struct cmp_hash_state *hash_state, size_t data_len, const void *data);

void cmp_hash_update_string(struct cmp_hash_state *hash_state, const char *string);

struct cmp_hash_state *cmp_hash_copy(const struct cmp_hash_state *hash_state);

void cmp_hash_finish(struct cmp_hash_state *hash_state, char hash[HASH_SIZE]);

int cmp_hash_cmp(const char hash1[HASH_SIZE], const char hash2[HASH_SIZE]);


unsigned int cmp_hash_hashtab_hash(hashtab_t hashtab, const_hashtab_key_t key1);

int cmp_hash_hashtab_cmp(hashtab_t hashtab, const_hashtab_key_t key1, const_hashtab_key_t key2);


int cmp_hash_qsort_cmp(const void *a, const void *b);

struct cmp_sim {
    size_t common;
    size_t left;
    size_t right;
};

void cmp_sim_add(struct cmp_sim *a, const struct cmp_sim *b);

double cmp_sim_rate(const struct cmp_sim *sim);

int cmp_sim_cmp(const struct cmp_sim *sim1, const struct cmp_sim *sim2);

#endif
