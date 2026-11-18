#!/bin/sh
# Install the PowerVR Mesa build to /opt/mesa-pvr for mainline kernels on the VisionFive 2.
# The vendor 6.12 kernel keeps the vendor Mesa; nothing here applies when booted on it.
# Usage: install.sh [release-tag|path/to/mesa-pvr-*.tar.gz]   (default: newest mesa-* release)
set -eu
REPO=${VF2_KERNEL_REPO:-temidaradev/visionfive2-patched-kernel}
[ "$(id -u)" = 0 ] || exec sudo "$0" "$@"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
if [ -f "${1:-}" ]; then
  cp "$1" "$T/m.tar.gz"
else
  TAG=${1:-$(curl -fsSL "https://api.github.com/repos/$REPO/releases?per_page=50" | python3 -c 'import json,sys; print(next(r["tag_name"] for r in json.load(sys.stdin) if r["tag_name"].startswith("mesa-")))')}
  NAME=mesa-pvr-${TAG#mesa-}-riscv64.tar.gz
  URL=https://github.com/$REPO/releases/download/$TAG/$NAME
  curl -fsSL "$URL" -o "$T/m.tar.gz"
  curl -fsSL "$URL.sha256" | awk '{print $1"  '"$T"'/m.tar.gz"}' | sha256sum -c - >/dev/null
fi
tar --no-same-owner -xzf "$T/m.tar.gz" -C "$T"
rm -rf /opt/mesa-pvr.new && mv "$T/opt/mesa-pvr" /opt/mesa-pvr.new
rm -rf /opt/mesa-pvr && mv /opt/mesa-pvr.new /opt/mesa-pvr
ICD=$(ls /opt/mesa-pvr/share/vulkan/icd.d/powervr_mesa_icd*.json | head -1)

# OpenGL/GLES through Zink on PowerVR, per application: pvr-gl <command>.
cat > /usr/local/bin/pvr-gl <<WRAP
#!/bin/sh
# Run a program with Mesa's Zink (OpenGL on Vulkan) over the PowerVR driver (mainline only).
case "\$(uname -r)" in *-starfive) echo "pvr-gl: needs a mainline kernel" >&2; exit 1;; esac
export LD_LIBRARY_PATH=/opt/mesa-pvr/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}
export LIBGL_DRIVERS_PATH=/opt/mesa-pvr/lib/dri
export GBM_BACKENDS_PATH=/opt/mesa-pvr/lib/gbm
export MESA_LOADER_DRIVER_OVERRIDE=zink
export VK_ICD_FILENAMES=$ICD
export PVR_I_WANT_A_BROKEN_VULKAN_DRIVER=1
exec "\$@"
WRAP
chmod 755 /usr/local/bin/pvr-gl

# Vulkan system-wide, but only on mainline: env-per-kernel copies this file to /etc/environment.
ENVF=/etc/environment.mainline
[ -f "$ENVF" ] || : > "$ENVF"
python3 - "$ENVF" "$ICD" <<'PY'
import re, sys
path, icd = sys.argv[1:]
s = open(path).read()
s = re.sub(r"# >>> mesa-pvr >>>.*?# <<< mesa-pvr <<<\n?", "", s, flags=re.S)
s = s.rstrip("\n") + f"""
# >>> mesa-pvr >>>
# PowerVR BXE-4-32 Vulkan (Mesa imagination driver, not yet marked conformant upstream).
VK_ICD_FILENAMES={icd}
PVR_I_WANT_A_BROKEN_VULKAN_DRIVER=1
# <<< mesa-pvr <<<
"""
open(path, "w").write(s.lstrip("\n"))
PY
[ -x /usr/local/sbin/env-per-kernel ] && /usr/local/sbin/env-per-kernel || true
echo "installed $(ls /opt/mesa-pvr/lib/libvulkan_powervr_mesa.so 2>/dev/null || echo /opt/mesa-pvr); ICD $ICD"
case "$(uname -r)" in *-starfive) echo "active after booting a mainline kernel";; *) echo "active now for new sessions";; esac
