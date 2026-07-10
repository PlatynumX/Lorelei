#ifndef ROTT64_N64_DIRENT_H
#define ROTT64_N64_DIRENT_H

/*
 * Minimal read-only dirent compatibility for the N64 target.
 *
 * Taradino includes <dirent.h> from rt_def.h for every translation unit,
 * while libdragon/newlib intentionally reports that POSIX directory streams
 * are unsupported. ROTT64 uses a fixed DragonFS data directory and direct
 * fopen() lookups, so directory enumeration is not required for the first
 * gameplay target. These stubs make optional scans behave as "no entries".
 */

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct rott64_dir_stream {
    int unused;
} DIR;

struct dirent {
    unsigned char d_type;
    char d_name[256];
};

#ifndef DT_UNKNOWN
#define DT_UNKNOWN 0
#endif
#ifndef DT_DIR
#define DT_DIR 4
#endif
#ifndef DT_REG
#define DT_REG 8
#endif

static inline DIR *opendir(const char *path)
{
    (void)path;
    return NULL;
}

static inline DIR *fdopendir(int fd)
{
    (void)fd;
    return NULL;
}

static inline struct dirent *readdir(DIR *directory)
{
    (void)directory;
    return NULL;
}

static inline int closedir(DIR *directory)
{
    (void)directory;
    return 0;
}

static inline void rewinddir(DIR *directory)
{
    (void)directory;
}

static inline long telldir(DIR *directory)
{
    (void)directory;
    return 0;
}

static inline void seekdir(DIR *directory, long location)
{
    (void)directory;
    (void)location;
}

static inline int dirfd(DIR *directory)
{
    (void)directory;
    return -1;
}

#ifdef __cplusplus
}
#endif

#endif /* ROTT64_N64_DIRENT_H */
