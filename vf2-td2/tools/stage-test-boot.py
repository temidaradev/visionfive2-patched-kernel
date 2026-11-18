#!/usr/bin/env python3
"""Run as root on the board; preserve the current kernel, DTB and boot default."""
from pathlib import Path
import datetime
import re
import subprocess

conf = Path('/boot/extlinux/extlinux.conf')
original = conf.read_text()
assert re.search(r'^default td2$', original, re.M)
assert 'label td2module' not in original
match = re.search(r'^label td2\n.*?(?=^label |\Z)', original, re.M | re.S)
assert match
entry = match[0]
assert '\tlinux /vmlinuz-6.12.5-starfive\n' in entry
assert '\tfdt /td2-fixed.dtb\n' in entry
assert 'initcall_blacklist=' not in entry
assert Path('/home/user/td2-drm-module/td2_drm.ko').is_file()

stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup = Path('/home/user/td2-drm-module') / ('extlinux-before-' + stamp + '.conf')
backup.write_text(original)
entry = entry.replace('label td2\n', 'label td2module\n', 1)
entry = re.sub(r'^\tmenu label .*$', '\tmenu label Stock kernel - deferred display module test', entry, flags=re.M)
entry = re.sub(r'^(\tappend .*)$', r'\1 initcall_blacklist=vs_drm_init', entry, flags=re.M)

# Restore the normal default as soon as userspace starts. The test module is
# loaded manually over SSH only after this restoration is verified.
restore = Path('/usr/local/sbin/td2-restore-boot-default')
restore.write_text('''#!/usr/bin/python3
from pathlib import Path
import os
p = Path('/boot/extlinux/extlinux.conf')
s = p.read_text()
if 'default td2module\\n' in s:
    p.write_text(s.replace('default td2module\\n', 'default td2\\n', 1))
    os.sync()
''')
restore.chmod(0o755)
unit = Path('/etc/systemd/system/td2-restore-boot-default.service')
unit.write_text('''[Unit]
Description=Restore normal boot default before manual display module test
After=local-fs.target
Before=display-manager.service
RequiresMountsFor=/boot

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/td2-restore-boot-default
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
''')
subprocess.run(['systemctl', 'daemon-reload'], check=True)
subprocess.run(['systemctl', 'enable', 'td2-restore-boot-default.service'], check=True)
staged = original.replace('default td2\n', 'default td2module\n', 1) + '\n' + entry
conf.write_text(staged)
subprocess.run(['sync'], check=True)
assert conf.read_text() == staged
print('Original configuration saved to', backup)
print(conf.read_text())
