#!/usr/bin/python3
"""Run with sudo on the board. Select original stock display boot for next reboot."""
from pathlib import Path
import os, re
assert os.geteuid() == 0, 'Run with sudo'
p = Path('/boot/extlinux/extlinux.conf')
s = p.read_text()
assert 'label td2\n' in s
new, count = re.subn(r'^default \S+$', 'default td2', s, flags=re.M)
assert count == 1
p.write_text(new)
os.sync()
print('Stock td2 boot selected. Reboot when ready; no files or backups removed.')
