# Raspberry Pi Touch Display 2 on the VisionFive 2

This directory makes the Raspberry Pi Touch Display 2 (5-inch, 720x1280, two
DSI lanes) work on a StarFive VisionFive 2 v1.3B. It runs on StarFive's Debian
image with the **stock** `6.12.5-starfive` kernel, and gives working picture,
backlight and touch.

The kernel tree at the root of this repository is StarFive's
`JH7110_VF2_6.12_v6.0.0` (first commit), plus the in-tree panel and regulator
drivers (second commit). Everything here is built as out-of-tree modules against
that tree, so the distro kernel keeps booting. Kernels built on the board
itself never booted.

## How it works

The vendor display pipeline is built into the stock kernel. It binds at about
6.2 s, before the panel driver can load, and `vs_simple_enc` swallows
`-EPROBE_DEFER`, so DRM comes up without a DSI connector. Instead of rebuilding
the kernel:

1. The `td2desktop` boot entry passes
   `initcall_blacklist=vs_drm_init,cdns_dsi_platform_driver_init`, which keeps
   the built-in display and DSI drivers from initialising at all.
2. After boot, `td2-display.service` (before the display manager) loads modules
   built from patched copies of those drivers, in order:
   `panel-ilitek-ili9881c` → `td2_dsi` → `td2_drm` → `td2_touch`.

| Path | What |
|---|---|
| `modules/td2-drm/` | Verisilicon DC/DRM (`td2_drm.ko`), Cadence DSI (`td2_dsi.ko`) and panel sources, with build scripts |
| `modules/td2-touch/` | Goodix GT911 driver in polling mode (`td2_touch.ko`), because the touch IRQ isn't wired on the Pi ribbon |
| `patches/` | Changes against the vendor drivers: `cadence-dsi.patch` (wakeup timing; arm DSI in `pre_enable` before DPI streams), `vs-dc-sync.patch`, `encoder.patch` (return `-EPROBE_DEFER` instead of swallowing it) |
| `prebuilt/6.12.5-starfive/` | The modules that currently boot on the board, with `SHA256SUMS` |
| `boot/` | `td2-fixed.dtb` (the booted DTB), the DT overlay source and `.dtbo`, the `td2desktop` extlinux entry, and the kernel config |
| `system/` | systemd units, `/usr/local/sbin` scripts, and the `/etc` module, initramfs and blacklist configuration |
| `tools/` | Bring-up and debug helpers: KMS and framebuffer patterns, DSI register dumps, touch event reader, boot staging scripts |

## Install on a VisionFive 2 (stock 6.12.5-starfive)

```sh
sudo install -d /usr/local/lib/td2/6.12.5-starfive
sudo install -m 644 prebuilt/6.12.5-starfive/{panel-ilitek-ili9881c,td2_dsi,td2_drm,td2_touch}.ko /usr/local/lib/td2/6.12.5-starfive/
sudo install -m 644 prebuilt/6.12.5-starfive/{fixed,gpio-regmap,pwm_bl,rpi-panel-v2-regulator}.ko /lib/modules/6.12.5-starfive/extra/
sudo depmod 6.12.5-starfive
sudo install -m 755 system/sbin/* /usr/local/sbin/
sudo install -m 644 system/systemd/* /etc/systemd/system/
sudo install -m 644 system/etc/modules /etc/modules
sudo install -m 644 system/etc/initramfs-modules /etc/initramfs-tools/modules
sudo install -m 755 system/etc/initramfs-hook-td2-gpu-firmware /etc/initramfs-tools/hooks/td2-gpu-firmware
sudo install -m 644 boot/td2-fixed.dtb /boot/
sudo update-initramfs -u -k 6.12.5-starfive
sudo systemctl enable td2-display.service td2-restore-boot-default.service
```

Then add `boot/extlinux-td2desktop.conf` to `/boot/extlinux/extlinux.conf`
and make it the default. Keep a known-good entry, because without a serial
console a bad boot can only be undone from another machine.

Identify the panel before using any of this: register `0x01` at I2C `0x45` on
bus 2 reads `0x09` on the 5-inch panel (`0x01` or `0x04` means the 7-inch).
