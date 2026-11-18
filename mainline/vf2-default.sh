#!/bin/sh
# Choose the default kernel on the VisionFive 2.
#   vf2-default mainline   boot the extlinux "mainline" entry by default (with a boot counter:
#                          two failed boots in a row fall back to the vendor 6.12 kernel)
#   vf2-default vendor     boot the extlinux default (vendor 6.12) again
#   vf2-default            show the current setting
set -eu
[ "$(id -u)" = 0 ] || exec sudo "$0" "$@"
CONF=/boot/extlinux/extlinux.conf
case "${1:-status}" in
  mainline)
    python3 - "$CONF" /boot/default.env <<'PY'
import re, sys
src, dst = sys.argv[1:]
m = re.search(r"^label mainline\n((?:\t.*\n?)*)", open(src).read(), re.M)
if not m:
    sys.exit("no 'mainline' entry in extlinux.conf; run mainline/install.sh first")
get = lambda k: re.search(rf"^\t{k} (.*)$", m.group(1), re.M).group(1).strip()
append = get("append") + " vf2.default=1 panic=10 systemd.watchdog_sec=60"
open(dst, "w").write(f"once_kernel={get('linux')}\nonce_fdt={get('fdt')}\nonce_bootargs={append}\n")
PY
    printf 0 > /boot/boot-tries; printf 1 > /boot/boot-tries.1; printf 2 > /boot/boot-tries.2
    sync
    echo "default: mainline ($(sed -n 's/^once_kernel=//p' /boot/default.env)); falls back to vendor after 2 failed boots" ;;
  vendor)
    rm -f /boot/default.env; sync
    echo "default: vendor kernel ($(sed -n 's/^default //p' "$CONF"))" ;;
  status)
    if [ -f /boot/default.env ]; then
      echo "default: mainline ($(sed -n 's/^once_kernel=//p' /boot/default.env)), failed tries: $(cat /boot/boot-tries 2>/dev/null || echo ?)/2"
    else
      echo "default: vendor kernel ($(sed -n 's/^default //p' "$CONF"))"
    fi
    echo "running: $(uname -r)" ;;
  *) echo "usage: vf2-default [mainline|vendor]" >&2; exit 2 ;;
esac
