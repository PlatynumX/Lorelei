#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(void)
{
    const char *path = "build-host/rott64-posix-stub-test.tmp";
    FILE *file = fopen(path, "wb");
    char cwd[32];
    char too_small[4];

    assert(file != NULL);
    assert(fputs("test", file) >= 0);
    assert(fclose(file) == 0);

    assert(access(path, F_OK) == 0);
    assert(access(path, R_OK) == 0);

    errno = 0;
    assert(access(path, W_OK) == -1);
    assert(errno == EROFS);

    assert(getcwd(cwd, sizeof(cwd)) == cwd);
    assert(strcmp(cwd, "rom:/rott") == 0);

    errno = 0;
    assert(getcwd(too_small, sizeof(too_small)) == NULL);
    assert(errno == ERANGE);

    assert(chdir("ignored-on-fixed-rom-filesystem") == 0);
    assert(remove(path) == 0);

    puts("N64 POSIX compatibility tests passed");
    return 0;
}
