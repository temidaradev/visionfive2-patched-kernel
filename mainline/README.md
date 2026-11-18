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

## GPU: blocked on the JH7110 (no uncached CPU mappings)

The kernel side gets as far as it can:

- `vf2-gpu.py` adds the GPU to the device tree, with a `simple-pm-bus` for the
  extra clocks and both GPU resets.
- The core clock runs at the vendor's 594 MHz, and the PMU hardware turn-off
  events are cleared.
- Imagination's open firmware `rogue_36.50.54.182_v1.fw` loads with
  `powervr.exp_hw_support=1`.

But the firmware **fails to boot almost every time** ("Firmware failed to boot",
-110). It succeeded once in five boots.

Things ruled out on hardware:

- memory above 4 GB (`mem=3G`);
- the display controller (held back with `initcall_blacklist=vs_dc_platform_driver_init`);
- clock rates (PLL2 1188 MHz, `gpu_core` 594 MHz);
- CMA on vs. off.

The likely cause is cache coherency. `drm/imagination` and Mesa share memory with
the GPU firmware through write-combined mappings, which assumes the CPU can map
memory uncached. The JH7110's U74 cores have no `Svpbmt` (and no T-Head MAE),
so those mappings stay **cached**. CPU writes sit in L1/L2 and the firmware reads
stale data, which fits the random results. StarFive's vendor DDK works around it
with explicit L2 flushes (`do_sifive_l2_flush64_range`).

Making it work would need explicit cache maintenance in the kernel driver
(firmware/CCB writes) and in Mesa (user BO writes). Until then, use the vendor 6.12
kernel for GPU acceleration. `mesa/` (PowerVR Vulkan plus Zink build) is kept
for when the kernel side works.

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
