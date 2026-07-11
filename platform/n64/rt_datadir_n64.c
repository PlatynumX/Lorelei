/* Read-only N64 data-directory backend for Taradino. */
#include "rt_datadir.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ROTT64_DATA_DIR "rom://rott"

char *datadir;

static char *duplicate_string(const char *text)
{
    const size_t length = strlen(text) + 1u;
    char *copy = malloc(length);
    if (copy != NULL) {
        memcpy(copy, text, length);
    }
    return copy;
}

static int file_exists(const char *path)
{
    FILE *file = fopen(path, "rb");
    if (file == NULL) {
        return 0;
    }
    fclose(file);
    return 1;
}

static char *make_path(const char *name, int uppercase)
{
    const size_t root_length = strlen(ROTT64_DATA_DIR);
    const size_t name_length = strlen(name);
    char *path = malloc(root_length + 1u + name_length + 1u);
    if (path == NULL) {
        return NULL;
    }

    memcpy(path, ROTT64_DATA_DIR, root_length);
    path[root_length] = '/';
    for (size_t index = 0; index < name_length; ++index) {
        const unsigned char value = (unsigned char)name[index];
        path[root_length + 1u + index] = uppercase ? (char)toupper(value) : (char)value;
    }
    path[root_length + 1u + name_length] = '\0';
    return path;
}

char *GetPrefDir(void)
{
    /* The first-level candidate is intentionally read-only. */
    return duplicate_string(ROTT64_DATA_DIR);
}

char *FindFileByName(const char *name)
{
    char *path;

    if (name == NULL || *name == '\0') {
        return NULL;
    }

    path = make_path(name, 0);
    if (path != NULL && file_exists(path)) {
        return path;
    }
    free(path);

    /* DragonFS is case-sensitive; official DOS data names are uppercase. */
    path = make_path(name, 1);
    if (path != NULL && file_exists(path)) {
        return path;
    }
    free(path);
    return NULL;
}

const char **GetDataDirs(int *num)
{
    static const char *directories[] = { ROTT64_DATA_DIR };
    if (num != NULL) {
        *num = 1;
    }
    return directories;
}
