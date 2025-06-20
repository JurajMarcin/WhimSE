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

#include "cmp_common.h"

#include <error.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#include <openssl/evp.h>

#include "mem.h"

void cmp_hash(size_t data_len, const void *data, char hash[HASH_SIZE])
{
    struct cmp_hash_state *hash_state = cmp_hash_begin(NULL);
    cmp_hash_update(hash_state, data_len, data);
    cmp_hash_finish(hash_state, hash);
}

struct cmp_hash_state {
    EVP_MD_CTX *ctx;
};

struct cmp_hash_state *cmp_hash_begin(const char *flavor)
{
    struct cmp_hash_state *hash_state = mem_alloc(sizeof(*hash_state));
    hash_state->ctx = EVP_MD_CTX_new();
    mem_check(hash_state->ctx);
    const EVP_MD *md = EVP_sha256();
    if (!EVP_DigestInit_ex(hash_state->ctx, md, NULL)) {
        error(EXIT_FAILURE, 0, "Failed to initialize hash state");
    }
    if (flavor) {
        cmp_hash_update_string(hash_state, flavor);
    }
    return hash_state;
}

void cmp_hash_update(struct cmp_hash_state *hash_state, size_t data_len,
                     const void *data)
{
    if (!EVP_DigestUpdate(hash_state->ctx, data, data_len)) {
        error(EXIT_FAILURE, 0,
              "Failed to update hash state with data of length %zu", data_len);
    }
}

void cmp_hash_update_string(struct cmp_hash_state *hash_state,
                            const char *string)
{
    cmp_hash_update(hash_state, strlen(string) + 1, string);
}

struct cmp_hash_state *cmp_hash_copy(const struct cmp_hash_state *hash_state)
{
    struct cmp_hash_state *new_hash_state = mem_alloc(sizeof(*hash_state));
    new_hash_state->ctx = EVP_MD_CTX_dup(hash_state->ctx);
    mem_check(new_hash_state->ctx);
    return new_hash_state;
}

void cmp_hash_finish(struct cmp_hash_state *hash_state, char hash[HASH_SIZE])
{
    unsigned char
        md[EVP_MAX_MD_SIZE > HASH_SIZE ? EVP_MAX_MD_SIZE : HASH_SIZE] = { 0 };
    if (!EVP_DigestFinal_ex(hash_state->ctx, md, NULL)) {
        error(EXIT_FAILURE, 0, "Failed to finalize hash state");
    }
    EVP_MD_CTX_free(hash_state->ctx);
    mem_free(hash_state);
    if (hash) {
        memcpy(hash, md, HASH_SIZE);
    }
}

int cmp_hash_cmp(const char hash1[HASH_SIZE], const char hash2[HASH_SIZE])
{
    if (!hash1 && !hash2) {
        return 0;
    }
    if (!hash1) {
        return -1;
    }
    if (!hash2) {
        return 1;
    }
    return memcmp(hash1, hash2, HASH_SIZE);
}

void cmp_hash_to_string(const char hash[HASH_SIZE],
                        char string[HASH_SIZE * 2 + 1])
{
    for (size_t i = 0; i < HASH_SIZE; i++) {
        sprintf(&string[i * 2], "%02hhx", (unsigned char)hash[i]);
    }
    string[HASH_SIZE * 2] = '\0';
}

unsigned int cmp_hash_hashtab_hash(hashtab_t hashtab, const_hashtab_key_t key)
{
    size_t mod = hashtab->size ? hashtab->size : 1;
    return ((const unsigned int *)key)[0] % mod;
}

int cmp_hash_hashtab_cmp(__attribute__((unused)) hashtab_t hashtab,
                         const_hashtab_key_t key1, const_hashtab_key_t key2)
{
    return cmp_hash_cmp(key1, key2);
}

int cmp_hash_qsort_cmp(const void *a, const void *b)
{
    return cmp_hash_cmp(a, b);
}

void cmp_sim_add(struct cmp_sim *a, const struct cmp_sim *b)
{
    a->common += b->common;
    a->left += b->left;
    a->right += b->right;
}

double cmp_sim_rate(const struct cmp_sim *sim)
{
    return (double)sim->common / (sim->common + sim->left + sim->right);
}

int cmp_sim_cmp(const struct cmp_sim *sim1, const struct cmp_sim *sim2)
{
    double rate1 = cmp_sim_rate(sim1);
    double rate2 = cmp_sim_rate(sim2);
    if (rate1 < rate2) {
        return -1;
    }
    if (rate1 > rate2) {
        return 1;
    }
    return 0;
}
