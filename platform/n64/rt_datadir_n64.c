/* N64 data-directory backend with runtime Shareware / Full / Custom selection. */
#include "rt_datadir.h"
#include "n64_platform.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#define ROTT64_SHAREWARE_DIR "rom://rott"
#define ROTT64_FULL_DIR "rom://rott/full"
#define ROTT64_CUSTOM_DIR "rom://rott/custom"
#define ROTT64_SAVE_DIR "sd:/"

char *datadir;

static char *duplicate_string(const char *text)
{
    const size_t length = strlen(text) + 1u;
    char *copy = malloc(length);
    if (copy != NULL) memcpy(copy, text, length);
    return copy;
}

static int file_exists(const char *path)
{
    FILE *file = fopen(path, "rb");
    if (file == NULL) return 0;
    fclose(file);
    return 1;
}

static char *join_path(const char *root, const char *name)
{
    const size_t a = strlen(root), b = strlen(name);
    char *path = malloc(a + 1u + b + 1u);
    if (!path) return NULL;
    memcpy(path, root, a);
    path[a] = '/';
    memcpy(path + a + 1u, name, b + 1u);
    return path;
}

static int ends_with_ci(const char *name, const char *suffix)
{
    size_t a = strlen(name), b = strlen(suffix);
    return a >= b && strcasecmp(name + a - b, suffix) == 0;
}

static const char *full_name_for(const char *name)
{
    if (strcasecmp(name, "HUNTBGIN.WAD") == 0 || strcasecmp(name, "DARKWAR.WAD") == 0) return "DARKWAR.WAD";
    if (strcasecmp(name, "HUNTBGIN.RTL") == 0 || strcasecmp(name, "DARKWAR.RTL") == 0) return "DARKWAR.RTL";
    if (strcasecmp(name, "HUNTBGIN.RTC") == 0 || strcasecmp(name, "DARKWAR.RTC") == 0) return "DARKWAR.RTC";
    return name;
}

static const char *shareware_name_for(const char *name)
{
    if (strcasecmp(name, "DARKWAR.WAD") == 0) return "HUNTBGIN.WAD";
    if (strcasecmp(name, "DARKWAR.RTL") == 0) return "HUNTBGIN.RTL";
    if (strcasecmp(name, "DARKWAR.RTC") == 0) return "HUNTBGIN.RTC";
    return name;
}

char *GetPrefDir(void)
{
    return duplicate_string(ROTT64_SAVE_DIR);
}

char *FindFileByName(const char *name)
{
    rott64_data_mode_t mode;
    char *path;
    if (name == NULL || *name == '\0') return NULL;

    mode = n64_platform_data_mode();
    if (mode == ROTT64_DATA_CUSTOM) {
        const char *custom = n64_platform_custom_content();
        if (custom != NULL && ((ends_with_ci(name, ".RTL") && ends_with_ci(custom, ".RTL")) ||
                               (ends_with_ci(name, ".RTC") && ends_with_ci(custom, ".RTC")))) {
            path = join_path(ROTT64_CUSTOM_DIR, custom);
            if (path != NULL && file_exists(path)) return path;
            free(path);
        }
        /* Custom level packs use the full-version resource WAD and fall back
           to the stock full RTL/RTC when the selected package is the other type. */
        path = join_path(ROTT64_FULL_DIR, full_name_for(name));
        if (path != NULL && file_exists(path)) return path;
        free(path);
    } else if (mode == ROTT64_DATA_FULL) {
        path = join_path(ROTT64_FULL_DIR, full_name_for(name));
        if (path != NULL && file_exists(path)) return path;
        free(path);
    } else {
        const char *mapped = shareware_name_for(name);
        path = join_path(ROTT64_SHAREWARE_DIR, mapped);
        if (path != NULL && file_exists(path)) return path;
        free(path);
    }

    /* Final compatibility fallback: exact name in the embedded shareware root. */
    path = join_path(ROTT64_SHAREWARE_DIR, name);
    if (path != NULL && file_exists(path)) return path;
    free(path);
    return NULL;
}

const char **GetDataDirs(int *num)
{
    static const char *shareware[] = { ROTT64_SHAREWARE_DIR };
    static const char *full[] = { ROTT64_FULL_DIR, ROTT64_SHAREWARE_DIR };
    if (num != NULL) *num = n64_platform_data_mode() == ROTT64_DATA_SHAREWARE ? 1 : 2;
    return n64_platform_data_mode() == ROTT64_DATA_SHAREWARE ? shareware : full;
}
