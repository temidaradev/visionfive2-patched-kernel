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

## GPU: firmware and Vulkan work; rendering hangs (Mesa doesn't support this core yet)

Status on the PowerVR BXE-4-32 (BVNC 36.50.54.182), November 2026:

| Layer | Status |
|---|---|
| Kernel driver + firmware boot | ✅ boots on the first try (`vf2-gpu.py`) |
| Vulkan device (`mesa/`) | ✅ `vulkaninfo`: *PowerVR B-Series BXE-4-32 MC1*, Imagination open-source Mesa driver, Vulkan 1.2 |
| OpenGL ES via Zink | ✅ creates contexts: *zink Vulkan 1.2 (PowerVR B-Series BXE-4-32 MC1)*, OpenGL ES 3.1 |
| Rendering | ❌ the first geometry job hangs the GPU ("Guilty lockup, Data Master=Geometry") |

What `vf2-gpu.py` changes in the kernel driver for the JH7110:

- adds the GPU to the device tree (simple-pm-bus for the extra clocks, both resets, 594 MHz core clock) and clears the PMU hardware turn-off events, as the vendor DDK does;
- marks the GPU `dma-noncoherent`. The U74 cores can't map memory uncached (no Svpbmt), so every write-combined mapping drm/imagination relies on is really cached. It therefore writes back and invalidates firmware objects at each CPU<->firmware handoff and syncs all user BOs at job submit;
- **flushes the MIPS firmware page tables.** They were written through a cached vmap and never flushed, which is why the firmware almost never booted before.

Why rendering hangs: Mesa marks only 36.52.104.182 and 36.53.104.796 as working
(`pvr_device_is_conformant`). It has a device description for 36.50.54.182 but
no working rendering on it yet. A hang on the first geometry job is typical of
command streams that are slightly wrong for an untested core. Fixing it needs
work in Mesa's imagination driver, comparing against the vendor DDK.

Also not done yet: after a GPU hang, the hard-reset path doesn't run the cache
syncs, so the firmware doesn't come back (device lost until reboot).

Use the vendor 6.12 kernel for GPU acceleration. On mainline, run `vulkaninfo`
or `pvr-gl <app>` to test new Mesa builds. The user must be in the `render` and
`video` groups.

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
