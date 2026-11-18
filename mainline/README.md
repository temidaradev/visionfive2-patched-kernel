# Mainline Linux on the VisionFive 2 (HDMI)

Mainline Linux (7.4-rc3) for the VisionFive 2 v1.3B. It boots alongside the
vendor 6.12 kernel; that kernel stays the default.

Mainline doesn't describe the JH7110's display hardware yet. HDMI comes from
Michal Wilczynski's series *"drm: starfive: jh7110: Enable display subsystem"*
(v7, 2026-11-06, [patchwork](https://patchwork.kernel.org/project/linux-riscv/list/?series=1204213)).
That series builds on mainline's Verisilicon DC8200 and Innosilicon HDMI
drivers, and the copy in `patches/` is the one applied at build time.

| Works | Not on mainline |
|---|---|
| HDMI with a framebuffer console (built in, so boot messages show on screen) | Raspberry Pi Touch Display 2 (DSI): use the 6.12 entry |
| SD card root, Ethernet, USB via PCIe (all built in) | GPU acceleration: the JH7110's PowerVR GPU has no mainline DT node yet |
| kexec, for live test-boots of later kernels | |

## Install (on the board)

```sh
curl -fsSL https://raw.githubusercontent.com/temidaradev/visionfive2-patched-kernel/main/mainline/install.sh | sudo sh
```

The installer:

- adds a **`mainline`** entry to `/boot/extlinux/extlinux.conf` without changing
  the default, and saves the previous file as `extlinux.conf.before-mainline`;
- installs the kernel, DTB and modules;
- keeps only one mainline build at a time, because `/boot` is a 100 MB FAT
  partition.

To boot mainline, pick it from the U-Boot menu, which shows for 10 seconds.

## Build

GitHub Actions builds every change under `mainline/` and publishes a
`mainline-<release>` release. To build a different tag, run the
*mainline kernel* workflow manually. Locally, on a Linux host with
`gcc-riscv64-linux-gnu`:

```sh
mainline/build.sh v7.4-rc3 dist
```

`vf2-hdmi.config` is merged over `arch/riscv` `defconfig`. The build fails if
Kconfig silently drops any option from it.
