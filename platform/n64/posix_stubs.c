/*
 * Minimal POSIX compatibility for Taradino on libdragon/newlib.
 *
 * ROTT64 uses a fixed, read-only DragonFS data directory.  Taradino still
 * references access(), getcwd(), and chdir() in legacy desktop paths, while
 * the N64 C library declares but does not provide those symbols.  Keep the
 * semantics deliberately narrow instead of pretending the ROM filesystem is
 * a writable Unix filesystem.
 */
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#ifdef __N64__

#define ROTT64_LOGICAL_CWD "rom://rott"

int access(const char *path, int mode)
{
    FILE *file;

    if ((mode & ~(R_OK | W_OK | X_OK)) != 0) {
        errno = EINVAL;
        return -1;
    }

    /* DragonFS is read-only.  The flashcart SD filesystem is writable and is
       used for Taradino's native ROTTGAM?.ROT save files. */
    if ((mode & W_OK) != 0 && strncmp(path, "sd://", 5) != 0 && strncmp(path, "sd:/", 4) != 0) {
        errno = EROFS;
        return -1;
    }
    if ((mode & W_OK) != 0) {
        return 0;
    }
    if ((mode & X_OK) != 0) {
        errno = EACCES;
        return -1;
    }

    file = fopen(path, "rb");
    if (file == NULL) {
        return -1;
    }
    fclose(file);
    return 0;
}

char *getcwd(char *buffer, size_t size)
{
    const size_t required = sizeof(ROTT64_LOGICAL_CWD);

    if (size < required) {
        errno = ERANGE;
        return NULL;
    }

    memcpy(buffer, ROTT64_LOGICAL_CWD, required);
    return buffer;
}

int chdir(const char *path)
{
    /* All game-data paths are resolved absolutely under rom://rott. */
    (void)path;
    return 0;
}

#endif
