#!/usr/bin/env python3
from pathlib import Path
import sys
MARK = 'ROTT64_R103_PRESENT_WRAP_CALLSITE'

def die(msg):
    raise SystemExit('ERROR: ' + msg)

def ensure_include(path, text):
    if '#include "n64_platform.h"' in text:
        return text
    lines = text.splitlines(True)
    last = -1
    for i, line in enumerate(lines[:80]):
        if line.startswith('#include '):
            last = i
    if last >= 0:
        lines.insert(last + 1, '#include "n64_platform.h"\n')
        return ''.join(lines)
    return '#include "n64_platform.h"\n' + text

def main(argv):
    if len(argv) != 2:
        die('usage: r103_patch_generated_present_wrap.py generated/rott')
    root = Path(argv[1])
    if not root.is_dir():
        die('missing generated root ' + str(root))
    wrapped = []
    for path in sorted(root.rglob('*.c')):
        text = path.read_text(encoding='utf-8', errors='strict')
        if 'display_show(' not in text:
            continue
        changed = False
        lines = []
        for line in text.splitlines(True):
            if 'display_show(' in line and 'rott64_n64_display_show_crt_safe(' not in line:
                line = line.replace('display_show(', 'rott64_n64_display_show_crt_safe(')
                if MARK not in line:
                    line = line.rstrip('\n') + ' /* ' + MARK + ' */\n'
                changed = True
            lines.append(line)
        if changed:
            path.write_text(ensure_include(path, ''.join(lines)), encoding='utf-8', newline='\n')
            wrapped.append(str(path))
    report = Path('build/reports/r103-generated-present-wrap.txt')
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text('\n'.join(wrapped) + ('\n' if wrapped else ''), encoding='utf-8')
    print('PASS: ROTT64_R103_GENERATED_PRESENT_WRAP scanned generated/rott')
    print('PASS: generated display_show wrapped:', len(wrapped))
    for item in wrapped[:20]:
        print('  ' + item)
    return 0
if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
