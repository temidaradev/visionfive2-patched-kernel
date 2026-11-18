#!/usr/bin/python3
from pathlib import Path
import datetime, os, re, subprocess

assert os.geteuid() == 0
subprocess.run(['systemctl', 'is-active', '--quiet', 'td2-display.service'], check=True)
assert Path('/dev/dri/renderD128').exists()
assert Path('/sys/bus/i2c/devices/2-005d/driver').resolve().name == 'td2-goodix-poll'
assert 'initcall_blacklist=vs_drm_init,cdns_dsi_platform_driver_init' in Path('/proc/cmdline').read_text()
conf = Path('/boot/extlinux/extlinux.conf')
original = conf.read_text()
match = re.search(r'^label td2module\n.*?(?=^label |\Z)', original, re.M | re.S)
assert match
entry = match[0].replace('label td2module\n', 'label td2desktop\n', 1)
entry = re.sub(r'^\tmenu label .*$', '\tmenu label Touch Display 2 - landscape desktop', entry, flags=re.M)
new = original
if not re.search(r'^label td2desktop$', new, re.M):
    new += '\n' + entry
new, n = re.subn(r'^default \S+$', 'default td2desktop', new, flags=re.M)
assert n == 1
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup = Path('/home/user/td2-drm-module') / ('extlinux-before-final-' + stamp + '.conf')
backup.write_text(original)
conf.write_text(new)
os.sync()
assert conf.read_text() == new
assert 'label td2\n' in new and 'label l0\n' in new
print('Default is td2desktop; stock recovery entries td2 and l0 retained.')
print('Backup:', backup)
