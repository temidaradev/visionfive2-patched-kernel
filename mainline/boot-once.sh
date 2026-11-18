#!/bin/sh
# Boot the "mainline" extlinux entry exactly once, falling back to the default afterwards.
# Usage: boot-once.sh [entry]   then reboot. Needs u-boot-tools (mkimage).
set -eu
[ "$(id -u)" = 0 ] || exec sudo "$0" "$@"
ENTRY=${1:-mainline}
HERE=$(cd "$(dirname "$0")" && pwd)
CONF=/boot/extlinux/extlinux.conf
command -v mkimage >/dev/null || { echo "install u-boot-tools first" >&2; exit 1; }
mkimage -A riscv -T script -C none -n boot-once -d "$HERE/boot-once.cmd" /boot/boot.scr >/dev/null
python3 - "$CONF" "$ENTRY" /boot/extlinux/extlinux-once.conf <<'PY'
import re, sys
src, entry, dst = sys.argv[1:]
m = re.search(rf"^label {re.escape(entry)}\n(?:\t.*\n?)*", open(src).read(), re.M)
if not m:
    sys.exit(f"no '{entry}' entry in {src}")
open(dst, "w").write(f"default {entry}\nprompt 0\ntimeout 1\n\n{m.group(0)}")
PY
# Kernel, DTB and command line for boot.scr, taken from the entry (U-Boot env text format).
python3 - "$CONF" "$ENTRY" /boot/once.env <<'PY'
import re, sys
src, entry, dst = sys.argv[1:]
block = re.search(rf"^label {re.escape(entry)}\n((?:\t.*\n?)*)", open(src).read(), re.M).group(1)
get = lambda k: re.search(rf"^\t{k} (.*)$", block, re.M).group(1).strip()
open(dst, "w").write(f"once_kernel={get('linux')}\nonce_fdt={get('fdt')}\nonce_bootargs={get('append')}\n")
PY
rm -f /boot/once-log.txt
printf 0 > /boot/boot-once.clear
printf "${ARM:-1}" > /boot/boot-once
sync
echo "next boot: $([ "$(cat /boot/boot-once)" = 1 ] && echo "'$ENTRY' once, then back to the default" || echo "normal default (flag off)")"
