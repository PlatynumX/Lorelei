#!/usr/bin/env python3
from pathlib import Path
import sys

OLD = r"""long LoadFile(char *filename, void **bufferptr)
{
	int handle;
	long length;

	handle = SafeOpenRead(filename);
	length = filelength(handle);
	*bufferptr = SafeMalloc(length);
	SafeRead(handle, *bufferptr, length);
	close(handle);
	return length;
}"""

NEW = r"""long LoadFile(char *filename, void **bufferptr)
{
#ifdef __N64__
	/* ROTT64_R111_STDIO_LOADFILE:
	   Use the same stdio/fseek/ftell/fread path that successfully validates
	   N64 saves, but deliberately keep SafeMalloc/Z_Malloc unchanged. */
	FILE *fp;
	long length;
	long remaining;
	byte *dst;

	fp = fopen(filename, "rb");
	if (fp == NULL)
		Error("Error opening %s: %s", filename, strerror(errno));

	if (fseek(fp, 0, SEEK_END) != 0)
	{
		fclose(fp);
		Error("File seek failure for %s: %s", filename, strerror(errno));
	}

	length = ftell(fp);
	if (length < 0)
	{
		fclose(fp);
		Error("File length failure for %s: %s", filename, strerror(errno));
	}

	if (fseek(fp, 0, SEEK_SET) != 0)
	{
		fclose(fp);
		Error("File seek failure for %s: %s", filename, strerror(errno));
	}

	*bufferptr = SafeMalloc(length);
	dst = (byte *)*bufferptr;
	remaining = length;

	while (remaining > 0)
	{
		size_t want = remaining > 1024 ? 1024 : (size_t)remaining;
		size_t got = fread(dst, 1, want, fp);

		if (got != want)
		{
			fclose(fp);
			Error("File read failure reading %ld bytes from %s", remaining, filename);
		}

		dst += got;
		remaining -= (long)got;
	}

	fclose(fp);
	return length;
#else
	int handle;
	long length;

	handle = SafeOpenRead(filename);
	length = filelength(handle);
	*bufferptr = SafeMalloc(length);
	SafeRead(handle, *bufferptr, length);
	close(handle);
	return length;
#endif
}"""

MARK = "ROTT64_R111_STDIO_LOADFILE"


def fail(message: str) -> None:
    raise SystemExit("ERROR: " + message)


def verify(text: str) -> None:
    if text.count(NEW) != 1:
        fail("exact r111 LoadFile implementation is not present exactly once")
    if text.count(MARK) != 1:
        fail("r111 marker count is not exactly one")
    required = (
        'fp = fopen(filename, "rb");',
        "fseek(fp, 0, SEEK_END)",
        "length = ftell(fp);",
        "fseek(fp, 0, SEEK_SET)",
        "*bufferptr = SafeMalloc(length);",
        "size_t want = remaining > 1024 ? 1024 : (size_t)remaining;",
        "size_t got = fread(dst, 1, want, fp);",
        "remaining -= (long)got;",
    )
    for token in required:
        if token not in NEW:
            fail("internal r111 implementation lost token: " + token)

    # Preserve the desktop/Taradino path in the #else branch.
    for token in (
        "handle = SafeOpenRead(filename);",
        "length = filelength(handle);",
        "SafeRead(handle, *bufferptr, length);",
    ):
        if token not in NEW:
            fail("desktop LoadFile fallback lost token: " + token)


def main() -> int:
    if len(sys.argv) not in (2, 3):
        fail("usage: r111_patch_stdio_loadfile.py generated/rott [--check]")

    root = Path(sys.argv[1])
    path = root / "rt_util.c"
    if not path.is_file():
        fail("missing generated/rott/rt_util.c")

    check_only = len(sys.argv) == 3
    if check_only and sys.argv[2] != "--check":
        fail("only supported optional argument is --check")

    text = path.read_text(encoding="utf-8", errors="strict")

    if check_only:
        verify(text)
        print("PASS: exact r111 LoadFile implementation verified")
        return 0

    if NEW in text:
        verify(text)
        print("PASS: r111 LoadFile already applied and verified")
        return 0

    count = text.count(OLD)
    if count != 1:
        fail("expected exactly one verified r110 LoadFile block, found " + str(count))

    text = text.replace(OLD, NEW, 1)
    verify(text)

    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
    print("PASS: replaced N64 LoadFile with stdio read path")
    print("PASS: SafeMalloc/Z_Malloc allocation path intentionally unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
