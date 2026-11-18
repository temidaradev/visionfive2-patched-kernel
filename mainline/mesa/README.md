# Mesa for the VisionFive 2 GPU (mainline Linux)

This is a current Mesa for the JH7110's PowerVR BXE-4-32 (BVNC 36.50.54.182)
running on the open `drm/imagination` kernel driver, i.e. the `mainline` kernel
from this repo. It provides:

- **Vulkan**: Mesa's `imagination` driver. This core isn't marked conformant
  upstream yet, so it needs `PVR_I_WANT_A_BROKEN_VULKAN_DRIVER=1`.
- **OpenGL / GLES**: Zink (OpenGL on top of that Vulkan driver), opt-in per
  application.

It's installed to `/opt/mesa-pvr`. The vendor 6.12 kernel still uses StarFive's
own Mesa 22.3, which this doesn't replace or touch.

## Install (on the board)

```sh
curl -fsSL https://raw.githubusercontent.com/temidaradev/visionfive2-patched-kernel/main/mainline/mesa/install.sh | sudo sh
```

- **Vulkan** is enabled system-wide on mainline kernels only. The installer adds
  `VK_ICD_FILENAMES` and `PVR_I_WANT_A_BROKEN_VULKAN_DRIVER=1` to
  `/etc/environment.mainline`, which `env-per-kernel` applies at boot when the
  running kernel isn't `*-starfive`.
- **OpenGL through Zink** applies per program: `pvr-gl glmark2-es2`,
  `pvr-gl firefox`, and so on. The desktop session keeps the vendor Mesa's
  software GL until Zink on this GPU is proven stable.

Check it with `vulkaninfo --summary` on a mainline boot. It should list
`PowerVR B-Series BXE-4-32`.

## Build

GitHub Actions (`.github/workflows/mesa.yml`) builds every change here and
publishes a `mesa-<version>` release. To build another Mesa ref, run the
*mesa pvr* workflow manually. `build.sh` runs on an Ubuntu 24.04 x86-64 host in
two stages:

1. It builds Mesa's host shader compilers (`mesa_clc`, `vtn_bindgen2`,
   `pco_clc`) natively. They need LLVM 18, clang, libclc and
   SPIRV-LLVM-Translator.
2. It cross-compiles the drivers for riscv64 against an Ubuntu 22.04 riscv64
   sysroot (glibc 2.35, older than the board's 2.36), using the stage-1 tools
   via `-Dmesa-clc=system -Dprecomp-compiler=system`. LLVM isn't needed on the
   board.

The build fails if any library needs a glibc symbol newer than 2.36.
