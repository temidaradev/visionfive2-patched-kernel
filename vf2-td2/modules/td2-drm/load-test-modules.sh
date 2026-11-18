#!/bin/bash
set -euo pipefail
grep -q 'initcall_blacklist=vs_drm_init,cdns_dsi_platform_driver_init' /proc/cmdline
grep -q '^default td2$' /boot/extlinux/extlinux.conf
test ! -d /sys/bus/platform/drivers/cdns-dsi
test ! -d /sys/bus/platform/drivers/starfive
systemctl stop display-manager
/sbin/modprobe -r panel_ilitek_ili9881c
/sbin/insmod /home/user/td2-drm-module/panel-ilitek-ili9881c.ko
/sbin/insmod /home/user/td2-drm-module/td2_dsi.ko
test -L /sys/bus/mipi-dsi/devices/295d0000.mipi.0/driver
systemd-run --unit=td2-display-test /sbin/insmod /home/user/td2-drm-module/td2_drm.ko
