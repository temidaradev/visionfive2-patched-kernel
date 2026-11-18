#!/bin/sh
# Install a mainline kernel build from GitHub releases as an extra U-Boot boot entry.
# The current default entry is left untouched; pick "mainline" from the U-Boot menu.
# Usage: install.sh [release-tag|path/to/linux-*.tar.gz]   (default: newest mainline-* release)
set -eu
REPO=${VF2_KERNEL_REPO:-temidaradev/visionfive2-patched-kernel}
[ "$(id -u)" = 0 ] || exec sudo "$0" "$@"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
if [ -f "${1:-}" ]; then
  cp "$1" "$T/k.tar.gz"
else
  TAG=${1:-$(curl -fsSL "https://api.github.com/repos/$REPO/releases?per_page=30" | python3 -c 'import json,sys; print(next(r["tag_name"] for r in json.load(sys.stdin) if r["tag_name"].startswith("mainline-")))')}
  REL=${TAG#mainline-}
  URL=https://github.com/$REPO/releases/download/$TAG/linux-$REL.tar.gz
  curl -fsSL "$URL" -o "$T/k.tar.gz"
  curl -fsSL "$URL.sha256" | awk '{print $1"  '"$T"'/k.tar.gz"}' | sha256sum -c - >/dev/null
fi
tar --no-same-owner -xzf "$T/k.tar.gz" -C "$T"
SRC=$(find "$T" -mindepth 1 -maxdepth 1 -type d -name 'linux-*' | head -1)
REL=${SRC##*/linux-}
DTB=jh7110-starfive-visionfive-2-v1.3b.dtb
# /boot is a 100 MB FAT partition shared with the vendor kernel: keep exactly one
# mainline build there, and only what U-Boot needs (kernel + DTB).
for f in /boot/vmlinuz-*-vf2* /boot/config-*-vf2* /boot/System.map-*-vf2* /boot/mainline-*.dtb; do
  [ -e "$f" ] && rm -f "$f"
done
for d in /lib/modules/*-vf2*; do
  [ -d "$d" ] && [ "${d##*/}" != "$REL" ] && rm -rf "$d"
done
cp "$SRC/boot/vmlinuz-$REL" /boot/
cp "$SRC/boot/$DTB" "/boot/mainline-$REL.dtb"
rm -rf "/lib/modules/$REL" && cp -a "$SRC/lib/modules/$REL" /lib/modules/
cp "$SRC/boot/config-$REL" "$SRC/boot/System.map-$REL" "/lib/modules/$REL/"
depmod "$REL"
# Open-driver GPU firmware for the BXE-4-32 (Imagination's staging repo; not yet in linux-firmware).
FW=/lib/firmware/powervr/rogue_36.50.54.182_v1.fw
if [ ! -f "$FW" ]; then
  mkdir -p /lib/firmware/powervr
  curl -fsSL "https://gitlab.freedesktop.org/imagination/linux-firmware/-/raw/powervr/powervr/rogue_36.50.54.182_v1.fw" -o "$FW.new" && mv "$FW.new" "$FW" || echo "warning: GPU firmware download failed" >&2
fi
CONF=/boot/extlinux/extlinux.conf
cp "$CONF" "$CONF.before-mainline"
python3 - "$CONF" "$REL" <<'PY'
import re, sys
path, rel = sys.argv[1], sys.argv[2]
s = open(path).read()
s = re.sub(r"\nlabel mainline\n(?:\t.*\n)*", "\n", s)
s = s.rstrip("\n") + f"""

label mainline
	menu label Mainline Linux {rel} (HDMI; no Touch Display)
	linux /vmlinuz-{rel}
	fdt /mainline-{rel}.dtb
	append root=/dev/mmcblk1p4 rw rootwait console=tty0 console=ttyS0,115200 earlycon selinux=0 powervr.exp_hw_support=1
"""
open(path, "w").write(s)
PY
# Keep a mainline default (vf2-default) pointing at the kernel just installed.
if [ -f /boot/default.env ] && command -v vf2-default >/dev/null; then vf2-default mainline >/dev/null; fi
sync
echo "installed $REL as boot entry 'mainline' (default unchanged: $(grep -m1 '^default' $CONF))"
