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
| SD card root, Ethernet, USB via PCIe (all built in) | |
| | GPU acceleration: blocked by CPU cache coherency, see below |
| kexec, for live test-boots of later kernels | |

## GPU: StarFive's vendor driver, ported to 7.4

The GPU runs StarFive's vendor PowerVR driver (`img-rogue`, DDK 1.19, from the
6.12 BSP), ported to this kernel, with the vendor GL/Vulkan userspace already on
the board. The open `drm/imagination` driver is disabled: its firmware boots
here, but current Mesa can't render on this core (36.50.54.182).

| glmark2 (off-screen) | vendor 6.12 | 7.4 + ported driver |
|---|---|---|
| GL | PowerVR BXE-4-32, OpenGL ES 3.2 build 1.19 | same |
| build / texture / phong / refract FPS | 867 / 757 / 462 / 38 | 695 / 743 / 412 / 38 |
| score | 531 | 472 |

- `img/port.py` adapts the driver to 7.4 APIs: `__assign_str`, `pfn_t`, timer
  renames, `dma_fence_ops`, module namespaces and kbuild.
- It also builds the driver as a module (`pvrsrvkm.ko`). Built in, it would
  probe before `/lib/firmware` is mounted, because mainline boots without an
  initramfs.
- `img/vf2-img.py` adds the kernel-side hooks the driver expects:
  - `starfive_pmu_hw_event_turn_off_mask()`, plus the `soc/starfive/jh7110_pmu.h` header;
  - `sifive_l2_flush64_range()`;
  - the vendor GPU device-tree node;
  - the Kconfig and Makefile hooks.
- `build.sh` fetches `drivers/gpu/drm/img` from StarFive's tree at the commit
  the 6.12 kernel was built from.
- Firmware: `rgx.fw.36.50.54.182` and `rgx.sh.36.50.54.182` from the vendor image.
- On the board, `env-per-kernel` applies the vendor Mesa environment
  (`MESA_LOADER_DRIVER_OVERRIDE=pvr`, ...) whenever `pvrsrvkm` is present.

`vf2-gpu.py` and `mesa/` hold the open-driver work (cache coherency fixes,
Mesa build). Set `VF2_GPU` to anything but `vendor` to build that instead.

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

Without a serial console the U-Boot menu isn't visible, so boot it **once** with
`boot-once.sh` (needs `u-boot-tools`):

```sh
sudo ARM=1 mainline/boot-once.sh mainline && sudo reboot
```

This installs `/boot/boot.scr`, which the vendor U-Boot runs before extlinux.
If `/boot/boot-once` holds `1`, U-Boot overwrites it with `0` **before**
loading the kernel, then boots the `mainline` entry directly with `booti`. It
also patches the real RAM size into the DTB, as U-Boot's normal boot path does.
Any later reset (crash, hang, power-cycle) boots the normal default again.
U-Boot logs each step to `/boot/once-log.txt`.

A trial boot can't leave you without a screen. The one-shot command line adds
`vf2.trial=1 panic=10 systemd.watchdog_sec=60`:

- `vf2-trial-guard.service` reboots if no HDMI display is connected after
  2 minutes;
- a kernel panic reboots after 10 seconds;
- a full hang is reset by the JH7110 hardware watchdog.

Each of these returns to the default kernel, because the one-shot flag was
already cleared.

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
