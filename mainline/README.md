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
| PowerVR BXE-4-32 GPU (experimental, see below) | |
| kexec, for live test-boots of later kernels | |

## GPU (experimental)

The JH7110's PowerVR BXE-4-32 runs on the open `drm/imagination` driver:

- `vf2-gpu.py` adds the GPU to the device tree. A `simple-pm-bus` parent turns
  on the clocks the driver doesn't manage, and the driver takes both GPU resets.
- The kernel is booted with `powervr.exp_hw_support=1`, because this core isn't
  on the driver's fully-supported list yet.
- The firmware, `rogue_36.50.54.182_v1.fw`, comes from Imagination's staging
  repository (not in linux-firmware yet). `install.sh` installs it.
- Userspace needs a recent Mesa with the `imagination-experimental` Vulkan
  driver, which has this core. The board's vendor Mesa (22.3) is too old.

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
