#!/usr/bin/python3
from pathlib import Path
import datetime, os, pwd, shutil, subprocess

assert os.geteuid() == 0
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup = Path('/home/user/td2-drm-module') / ('install-backup-' + stamp)
backup.mkdir()
module_dir = Path('/usr/local/lib/td2/6.12.5-starfive')
module_dir.mkdir(parents=True, exist_ok=True)
for name in ('td2_drm.ko', 'td2_dsi.ko', 'panel-ilitek-ili9881c.ko'):
    shutil.copy2(Path('/home/user/td2-drm-module') / name, module_dir / name)
shutil.copy2('/home/user/td2-touch-module/td2_touch.ko', module_dir / 'td2_touch.ko')
for path in module_dir.iterdir():
    os.chown(path, 0, 0)
    path.chmod(0o644)

monitors = '''<monitors version="2">
  <configuration>
    <logicalmonitor>
      <x>0</x><y>0</y><scale>1</scale><primary>yes</primary>
      <transform><rotation>left</rotation><flipped>no</flipped></transform>
      <monitor>
        <monitorspec>
          <connector>DSI-1</connector><vendor>unknown</vendor>
          <product>unknown</product><serial>unknown</serial>
        </monitorspec>
        <mode><width>720</width><height>1280</height><rate>57.034465789794922</rate></mode>
      </monitor>
    </logicalmonitor>
  </configuration>
</monitors>
'''
for username, home in [('user', '/home/user'), ('Debian-gdm', '/var/lib/gdm3')]:
    who = pwd.getpwnam(username)
    config = Path(home) / '.config'
    config.mkdir(exist_ok=True)
    os.chown(config, who.pw_uid, who.pw_gid)
    p = config / 'monitors.xml'
    if p.exists():
        shutil.copy2(p, backup / (username + '-monitors.xml'))
    p.write_text(monitors)
    os.chown(p, who.pw_uid, who.pw_gid)
    p.chmod(0o644)

loader = Path('/usr/local/sbin/td2-display-start')
loader.write_text('''#!/bin/bash
set -euo pipefail
test "$(uname -r)" = 6.12.5-starfive
grep -q 'initcall_blacklist=vs_drm_init,cdns_dsi_platform_driver_init' /proc/cmdline
modules=/usr/local/lib/td2/6.12.5-starfive
test ! -d /sys/bus/platform/drivers/cdns-dsi
test ! -d /sys/bus/platform/drivers/starfive
# The stock panel may already be loaded by initramfs, but has no DSI host.
if test -d /sys/module/panel_ilitek_ili9881c; then
    /sbin/modprobe -r panel_ilitek_ili9881c
fi
/sbin/insmod "$modules/panel-ilitek-ili9881c.ko"
/sbin/insmod "$modules/td2_dsi.ko"
test -L /sys/bus/mipi-dsi/devices/295d0000.mipi.0/driver
/sbin/insmod "$modules/td2_drm.ko"
# The stock Goodix driver expects an IRQ unavailable on the Pi ribbon.
if test -L /sys/bus/i2c/devices/2-005d/driver; then
    printf '%s' 2-005d > /sys/bus/i2c/drivers/Goodix-TS/unbind
fi
/sbin/insmod "$modules/td2_touch.ko"
test "$(basename "$(readlink /sys/bus/i2c/devices/2-005d/driver)")" = td2-goodix-poll
udevadm settle
''')
loader.chmod(0o755)
unit = Path('/etc/systemd/system/td2-display.service')
unit.write_text('''[Unit]
Description=VisionFive 2 Touch Display 2 display and touch drivers
After=local-fs.target systemd-udev-settle.service td2-restore-boot-default.service
Before=display-manager.service
Wants=systemd-udev-settle.service
ConditionKernelCommandLine=initcall_blacklist=vs_drm_init,cdns_dsi_platform_driver_init

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/td2-display-start
RemainAfterExit=yes
TimeoutStartSec=45

[Install]
WantedBy=graphical.target
''')

# Firmware must be present when the built-in GPU probes before the rootfs.
hook = Path('/etc/initramfs-tools/hooks/td2-gpu-firmware')
hook.write_text('''#!/bin/sh
set -e
PREREQ=""
prereqs() { echo "$PREREQ"; }
case "$1" in prereqs) prereqs; exit 0;; esac
. /usr/share/initramfs-tools/hook-functions
copy_file firmware /lib/firmware/rgx.fw.36.50.54.182
copy_file firmware /lib/firmware/rgx.sh.36.50.54.182
''')
hook.chmod(0o755)
initrd = Path('/boot/initrd.img-6.12.5-starfive')
shutil.copy2(initrd, backup / initrd.name)
bootconf = Path('/boot/extlinux/extlinux.conf')
boottext = bootconf.read_text()
shutil.copy2(bootconf, backup / 'extlinux.conf')
subprocess.run(['update-initramfs', '-u', '-k', '6.12.5-starfive'], check=True)
# Kernel hooks must not discard the explicit test/recovery entries.
bootconf.write_text(boottext)
contents = subprocess.check_output(['lsinitramfs', str(initrd)], text=True)
assert 'rgx.fw.36.50.54.182' in contents
assert 'rgx.sh.36.50.54.182' in contents
subprocess.run(['systemctl', 'daemon-reload'], check=True)
subprocess.run(['systemctl', 'enable', 'td2-display.service'], check=True)
assert 'default td2\n' in boottext
bootconf.write_text(boottext.replace('default td2\n', 'default td2module\n', 1))
os.sync()
print('Installed boot test; normal default will be restored at startup.')
print('Backups:', backup)
