#!/usr/bin/env bash
# Build mainline Linux for the VisionFive 2 v1.3B with the JH7110 HDMI series.
# Usage: mainline/build.sh [tag] [outdir]   (Linux host with gcc-riscv64-linux-gnu)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
TAG=${1:-v7.4-rc3}; OUT=$(mkdir -p "${2:-out}" && cd "${2:-out}" && pwd)
export ARCH=riscv CROSS_COMPILE=${CROSS_COMPILE:-riscv64-linux-gnu-}
# GitHub's mirror is far more reliable from CI runners; kernel.org is the fallback.
if [ ! -d linux ]; then
  git clone -q --depth 1 --branch "$TAG" https://github.com/torvalds/linux.git ||
    git clone -q --depth 1 --branch "$TAG" https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
fi
cd linux
git -c user.name=build -c user.email=build@localhost am -q --3way "$HERE"/patches/*.mbox
# GPU: StarFive's vendor PowerVR driver (img-rogue), ported to this kernel. It works
# with the vendor GL/Vulkan userspace already on the board; the open drm/imagination
# driver can't render on this core with current Mesa.
export VF2_GPU=vendor
VENDOR_REV=4cecf169f38eb94b40e307f5f870055e4d9d64f1   # JH7110_VF2_6.12_v6.0.0
if [ ! -d ../vendor-img ]; then
  git init -q ../vendor-img
  git -C ../vendor-img remote add origin https://github.com/starfive-tech/linux.git
  git -C ../vendor-img sparse-checkout set drivers/gpu/drm/img
  git -C ../vendor-img fetch -q --depth 1 --filter=blob:none origin "$VENDOR_REV"
  git -C ../vendor-img checkout -q FETCH_HEAD
fi
rm -rf drivers/gpu/drm/img && cp -a ../vendor-img/drivers/gpu/drm/img drivers/gpu/drm/img
python3 "$HERE/img/port.py" .
python3 "$HERE/img/vf2-img.py"
python3 "$HERE/vf2-gpu.py"
git add -A && git -c user.name=build -c user.email=build@localhost commit -qm "vf2: vendor GPU driver and fixups"
make -s defconfig
scripts/kconfig/merge_config.sh -m -O . .config "$HERE/vf2-hdmi.config" >/dev/null
make -s olddefconfig
# Fail loudly if Kconfig dropped an option (missing dependency or renamed symbol).
missing=0
while IFS= read -r line; do
  case "$line" in CONFIG_*=*) grep -qxF "$line" .config || { echo "not applied: $line" >&2; missing=1; } ;; esac
done < "$HERE/vf2-hdmi.config"
[ "$missing" = 0 ]
make -s -j"$(nproc)" Image.gz dtbs modules
REL=$(make -s kernelrelease)
STAGE=$OUT/linux-$REL
rm -rf "$STAGE"; mkdir -p "$STAGE/boot"
cp arch/riscv/boot/Image.gz "$STAGE/boot/vmlinuz-$REL"
cp arch/riscv/boot/dts/starfive/jh7110-starfive-visionfive-2-v1.3b.dtb "$STAGE/boot/"
cp .config "$STAGE/boot/config-$REL"; cp System.map "$STAGE/boot/System.map-$REL"
make -s modules_install INSTALL_MOD_PATH="$STAGE" INSTALL_MOD_STRIP=1
tar -C "$OUT" -czf "$OUT/linux-$REL.tar.gz" "linux-$REL"
(cd "$OUT" && sha256sum "linux-$REL.tar.gz" > "linux-$REL.tar.gz.sha256")
echo "$REL" > "$OUT/release"
ls -la "$OUT"
