from pathlib import Path
import subprocess
p = Path('/boot/extlinux/extlinux.conf')
s = p.read_text()
assert 'default td2\n' in s
old = 'initcall_blacklist=vs_drm_init\n'
assert s.count(old) == 1
assert Path('/home/user/td2-drm-module/td2_dsi.ko').is_file()
s = s.replace('default td2\n', 'default td2module\n', 1)
s = s.replace(old, 'initcall_blacklist=vs_drm_init,cdns_dsi_platform_driver_init\n')
p.write_text(s)
subprocess.run(['sync'], check=True)
assert p.read_text() == s
print('Staged stock kernel with separately loadable display and DSI host.')
