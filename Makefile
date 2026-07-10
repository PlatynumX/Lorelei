.DEFAULT_GOAL := all

HOST_BUILD_DIR := build-host
HOST_CC ?= cc
HOST_WAD_TEST := $(HOST_BUILD_DIR)/test_wad
HOST_PLATFORM_TEST := $(HOST_BUILD_DIR)/test_platform
HOST_SDL_TEST := $(HOST_BUILD_DIR)/test_sdl_compat
HOST_DIRENT_TEST := $(HOST_BUILD_DIR)/test_dirent_stub
HOST_POSIX_TEST := $(HOST_BUILD_DIR)/test_posix_stubs

.PHONY: all clean distclean test-host test-tools reports prepare preflight

test-host:
	@mkdir -p $(HOST_BUILD_DIR)
	$(HOST_CC) -std=c11 -Wall -Wextra -Werror -Isrc src/wad.c tests/test_wad.c -o $(HOST_WAD_TEST)
	$(HOST_WAD_TEST)
	$(HOST_CC) -std=c11 -Wall -Wextra -Werror -Isrc src/indexed_video.c src/input_map.c tests/test_platform.c -o $(HOST_PLATFORM_TEST)
	$(HOST_PLATFORM_TEST)
	$(HOST_CC) -std=c11 -Wall -Wextra -Werror -Iplatform/n64 platform/n64/n64_platform.c platform/n64/sdl_n64.c platform/n64/sdl_mixer_stub.c platform/n64/vgatext_n64.c tests/test_sdl_compat.c -o $(HOST_SDL_TEST)
	$(HOST_SDL_TEST)
	$(HOST_CC) -std=c11 -Wall -Wextra -Werror -D__N64__=1 -Iplatform/n64 tests/test_dirent_stub.c -o $(HOST_DIRENT_TEST)
	$(HOST_DIRENT_TEST)
	$(HOST_CC) -std=c11 -Wall -Wextra -Werror -D__N64__=1 platform/n64/posix_stubs.c tests/test_posix_stubs.c -o $(HOST_POSIX_TEST)
	$(HOST_POSIX_TEST)
	python3 tests/test_tools.py

test-tools:
	python3 tests/test_tools.py

prepare:
	python3 tools/prepare_engine.py

preflight:
	python3 tools/preflight_engine.py generated/rott platform/n64

reports:
	@mkdir -p build/reports
	python3 tools/wad_inventory.py filesystem/rott/HUNTBGIN.WAD --out build/reports
	python3 tools/audit_taradino.py generated/rott --out build/reports
	@if [ -d vendor/rottds/source ]; then python3 tools/rottds_reference_report.py vendor/taradino/source/rott vendor/rottds/source --out build/reports; fi

clean:
	rm -rf build build-host rott64.z64 rott64.z64.sha256

distclean: clean
	rm -rf generated/rott vendor/taradino/source vendor/rottds/source

# Only load libdragon rules when a ROM target is actually requested. This keeps
# host tests and cleanup usable on machines without an N64 toolchain.
N64_GOALS := $(filter all rott64.z64,$(MAKECMDGOALS))
ifeq ($(strip $(MAKECMDGOALS)),)
N64_GOALS := all
endif

ifneq ($(strip $(N64_GOALS)),)
ifndef N64_INST
$(error N64_INST is not set; run this target inside the libdragon environment)
endif

BUILD_DIR := build
include $(N64_INST)/include/n64.mk

ENGINE_SOURCES := $(sort $(filter-out generated/rott/adlmusic.c generated/rott/sdlmusic.c,$(wildcard generated/rott/*.c)))
PLATFORM_SOURCES := platform/n64/n64_platform.c platform/n64/sdl_n64.c platform/n64/sdl_mixer_stub.c platform/n64/posix_stubs.c
ALL_SOURCES := $(ENGINE_SOURCES) $(PLATFORM_SOURCES)
OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(ALL_SOURCES))

CFLAGS += -std=gnu11 -O2 -G0 -ffast-math -fno-strict-aliasing
# Taradino's legacy optimized renderer/actor code triggers GCC's
# -Wmaybe-uninitialized analysis on several control-flow-heavy functions.
# Keep the diagnostics visible, but do not let this one warning class stop
# the MIPS build. All other libdragon -Werror diagnostics remain fatal.
CFLAGS += -Wno-error=maybe-uninitialized
CFLAGS += -Igenerated/rott -Iplatform/n64
CFLAGS += -DSHAREWARE=1 -D__N64__=1
CFLAGS += -DDATADIR='"rom:/rott"'
CFLAGS += -DPACKAGE_STRING='"ROTT64 Shareware First-Level Candidate"'
CFLAGS += -DPACKAGE_TARNAME='"rott64"'
CFLAGS += -DNO_NETWORK=1
LDFLAGS += -lm

all: preflight rott64.z64

rott64.z64: N64_ROM_TITLE = "ROTT64 SHAREWARE"
rott64.z64: $(BUILD_DIR)/rott64.elf $(BUILD_DIR)/rott64.dfs

$(BUILD_DIR)/rott64.dfs: $(shell find filesystem -type f 2>/dev/null)

$(BUILD_DIR)/rott64.elf: $(OBJS)

-include $(OBJS:.o=.d)
endif
