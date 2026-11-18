#!/usr/bin/env bash
# Build Mesa (PowerVR Vulkan + Zink) for the VisionFive 2 on mainline Linux.
# Runs in a Debian bookworm container: its riscv64 cross toolchain is gcc 12 with
# glibc 2.36, exactly the board's libc and libstdc++. Stage 1 builds Mesa's host
# shader compilers natively (LLVM 15/clang/libclc); stage 2 cross-compiles the
# drivers against an Ubuntu 22.04 riscv64 sysroot for the other libraries.
# Usage: mainline/mesa/build.sh [mesa-ref] [outdir]   (debian:bookworm x86-64)
set -euo pipefail
SUDO=$(command -v sudo || true)
REF=${1:-main}
OUT=$(mkdir -p "${2:-out}" && cd "${2:-out}" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${WORK:-$PWD/mesa-work}
PREFIX=/opt/mesa-pvr
SYSROOT=$WORK/sysroot
mkdir -p "$WORK"; cd "$WORK"

[ -d mesa ] || git clone -q https://gitlab.freedesktop.org/mesa/mesa.git
git -C mesa fetch -q origin "$REF" && git -C mesa checkout -q FETCH_HEAD
VERSION=$(cat mesa/VERSION)-$(git -C mesa rev-parse --short=10 HEAD)

# --- riscv64 sysroot (extract only; no emulation needed) ---
PKGS=libc6-dev,libdrm-dev,libwayland-dev,libwayland-egl-backend-dev,libx11-dev,libxext-dev,libxfixes-dev,libxcb1-dev,libxcb-dri3-dev,libxcb-present-dev,libxcb-sync-dev,libxcb-shm0-dev,libxcb-randr0-dev,libxcb-xfixes0-dev,libxcb-glx0-dev,libxcb-keysyms1-dev,libx11-xcb-dev,libxshmfence-dev,libxxf86vm-dev,libxrandr-dev,libexpat1-dev,zlib1g-dev,libzstd-dev,libudev-dev
if [ ! -d "$SYSROOT/usr/include" ]; then
  # Ubuntu Archive Automatic Signing Key (2018), which signs jammy.
  KR=$WORK/ubuntu-archive.asc
  curl -fsSL 'https://keyserver.ubuntu.com/pks/lookup?op=get&search=0xF6ECB3762474EDA9D21B7022871920D1991BC93C' -o "$KR"
  $SUDO mmdebstrap --keyring="$KR" --variant=extract --architectures=riscv64 --components=main,universe \
    --include="$PKGS" jammy "$SYSROOT" http://ports.ubuntu.com/ubuntu-ports
  $SUDO chown -R "$(id -u):$(id -g)" "$SYSROOT"
  # Absolute symlinks would point at the build host's root.
  python3 - "$SYSROOT" <<'PY'
import os, sys
root = os.path.abspath(sys.argv[1])
for d, _, fs in os.walk(root):
    for f in fs:
        p = os.path.join(d, f)
        if os.path.islink(p) and os.readlink(p).startswith("/"):
            t = root + os.readlink(p); os.unlink(p); os.symlink(os.path.relpath(t, d), p)
PY
fi

# --- stage 1: host tools ---
cat > native.ini <<INI
[binaries]
llvm-config = '/usr/bin/llvm-config-15'
INI
meson setup native-build mesa --native-file native.ini --prefix "$WORK/native" -Dbuildtype=release \
  -Dvulkan-drivers=imagination -Dgallium-drivers= -Dplatforms= -Dopengl=false -Dglx=disabled -Degl=disabled -Dgbm=disabled \
  -Dmesa-clc=enabled -Dinstall-mesa-clc=true -Dprecomp-compiler=enabled -Dinstall-precomp-compiler=true \
  -Dllvm=enabled -Dshared-llvm=enabled -Dvalgrind=disabled -Dlibunwind=disabled >/dev/null
ninja -C native-build install >/dev/null
export PATH=$WORK/native/bin:$PATH
command -v mesa_clc vtn_bindgen2 pco_clc

# --- stage 2: riscv64 drivers ---
# Cross pkg-config: the sysroot prefix must only apply to riscv64 lookups, not to
# build-machine tools like wayland-scanner.
PCLIBDIR=$SYSROOT/usr/lib/riscv64-linux-gnu/pkgconfig:$SYSROOT/usr/share/pkgconfig:$SYSROOT/usr/lib/pkgconfig
cat > "$WORK/pkg-config-riscv64" <<PC
#!/bin/sh
PKG_CONFIG_SYSROOT_DIR='$SYSROOT' PKG_CONFIG_LIBDIR='$PCLIBDIR' exec pkg-config "\$@"
PC
chmod +x "$WORK/pkg-config-riscv64"
# Mesa requires the build machine's wayland-scanner to match the target libwayland.
WLVER=$("$WORK/pkg-config-riscv64" --modversion wayland-client)
if [ ! -x "$WORK/native/bin/wayland-scanner" ] || [ "$("$WORK/native/bin/wayland-scanner" --version 2>&1 | grep -oE '[0-9.]+$')" != "$WLVER" ]; then
  rm -rf wl-src wl-build
  git clone -q --depth 1 --branch "$WLVER" https://gitlab.freedesktop.org/wayland/wayland.git wl-src
  meson setup wl-build wl-src --prefix "$WORK/native" --libdir lib -Dlibraries=false \
    -Ddocumentation=false -Dtests=false -Ddtd_validation=false >/dev/null
  ninja -C wl-build install >/dev/null
fi
"$WORK/native/bin/wayland-scanner" --version
cat > cross.ini <<INI
[binaries]
c = ['riscv64-linux-gnu-gcc', '--sysroot=$SYSROOT']
cpp = ['riscv64-linux-gnu-g++', '--sysroot=$SYSROOT']
ar = 'riscv64-linux-gnu-ar'
strip = 'riscv64-linux-gnu-strip'
pkg-config = '$WORK/pkg-config-riscv64'
[properties]
sys_root = '$SYSROOT'
pkg_config_libdir = ['$SYSROOT/usr/lib/riscv64-linux-gnu/pkgconfig', '$SYSROOT/usr/share/pkgconfig', '$SYSROOT/usr/lib/pkgconfig']
[built-in options]
c_args = ['-march=rv64gc', '-mabi=lp64d']
cpp_args = ['-march=rv64gc', '-mabi=lp64d']
[host_machine]
system = 'linux'
cpu_family = 'riscv64'
cpu = 'riscv64'
endian = 'little'
INI
meson setup cross-build mesa --cross-file cross.ini --prefix "$PREFIX" --libdir lib -Dbuildtype=release \
  -Dbuild.pkg_config_path="$WORK/native/lib/pkgconfig" \
  -Dvulkan-drivers=imagination -Dgallium-drivers=zink -Dplatforms=x11,wayland \
  -Dopengl=true -Dgles1=disabled -Dgles2=enabled -Degl=enabled -Dgbm=enabled -Dglx=dri -Dglvnd=disabled \
  -Dmesa-clc=system -Dprecomp-compiler=system -Dllvm=disabled -Dvalgrind=disabled -Dlibunwind=disabled \
  -Dzstd=enabled -Dvulkan-layers= -Dtools=
ninja -C cross-build >/dev/null
rm -rf "$WORK/stage" && DESTDIR="$WORK/stage" ninja -C cross-build install >/dev/null
find "$WORK/stage$PREFIX" -name '*.so*' -type f -exec riscv64-linux-gnu-strip --strip-unneeded {} + 2>/dev/null || true
# Highest glibc symbol version used must be <= 2.36 (the board).
maxglibc=$(find "$WORK/stage$PREFIX" -name '*.so*' -type f -exec riscv64-linux-gnu-objdump -T {} + 2>/dev/null | grep -oE 'GLIBC_2\.[0-9]+' | sort -uV | tail -1)
echo "max glibc symbol: $maxglibc"
[ "$(printf '%s\nGLIBC_2.36\n' "$maxglibc" | sort -V | tail -1)" = GLIBC_2.36 ]
maxcxx=$(find "$WORK/stage$PREFIX" -name '*.so*' -type f -exec riscv64-linux-gnu-objdump -T {} + 2>/dev/null | grep -oE 'GLIBCXX_3\.4\.[0-9]+' | sort -uV | tail -1)
echo "max libstdc++ symbol: ${maxcxx:-none}"
[ -z "$maxcxx" ] || [ "$(printf '%s\nGLIBCXX_3.4.30\n' "$maxcxx" | sort -V | tail -1)" = GLIBCXX_3.4.30 ]
NAME=mesa-pvr-$VERSION-riscv64
tar -C "$WORK/stage" -czf "$OUT/$NAME.tar.gz" opt
(cd "$OUT" && sha256sum "$NAME.tar.gz" > "$NAME.tar.gz.sha256")
echo "$VERSION" > "$OUT/version"
ls -la "$OUT"
