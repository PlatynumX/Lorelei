#include <dirent.h>

int main(void)
{
    DIR *directory = opendir("rom://rott");
    if (directory != 0) {
        return 1;
    }
    if (readdir(directory) != 0) {
        return 2;
    }
    rewinddir(directory);
    seekdir(directory, 0);
    if (telldir(directory) != 0) {
        return 3;
    }
    if (dirfd(directory) != -1) {
        return 4;
    }
    return closedir(directory);
}
