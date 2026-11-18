#!/usr/bin/env bash
# Build stable Linux 7.3 for the VisionFive 2 v1.3B with the JH7110 HDMI series backported.
# Usage: mainline/build.sh [tag] [outdir]   (Linux host with gcc-riscv64-linux-gnu)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
TAG=${1:-v7.3.5}; OUT=$(mkdir -p "${2:-out}" && cd "${2:-out}" && pwd)
export ARCH=riscv CROSS_COMPILE=${CROSS_COMPILE:-riscv64-linux-gnu-}
# Stable tags live in the stable tree; GitHub's mirror is more reliable from CI runners.
if [ ! -d linux ]; then
  git clone -q --depth 1 --branch "$TAG" https://github.com/gregkh/linux.git ||
    git clone -q --depth 1 --branch "$TAG" https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git
fi
cd linux
git -c user.name=build -c user.email=build@localhost am -q "$HERE"/patches/*.patch
python3 "$HERE/vf2-gpu.py"
git -c user.name=build -c user.email=build@localhost commit -qam "vf2: GPU device tree and power fixups"
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
