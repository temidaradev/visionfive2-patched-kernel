from pathlib import Path
import os
p = Path('/boot/extlinux/extlinux.conf')
s = p.read_text()
assert 'default td2\n' in s
assert s.count('initcall_blacklist=vs_drm_init,cdns_dsi_platform_driver_init') == 1
s = s.replace('default td2\n', 'default td2module\n', 1)
p.write_text(s)
os.sync()
assert p.read_text() == s
print('Re-armed deferred display test; recovery service remains enabled.')
