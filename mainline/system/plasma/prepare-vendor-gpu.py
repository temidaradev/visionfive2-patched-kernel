#!/usr/bin/env python3
"""Copy the installed StarFive driver into the separate Plasma rootfs."""
from pathlib import Path
import glob
import json
import shutil
import subprocess

root = Path('/opt/plasma68-root')
base = root / 'opt/vf2-gpu'
lib = base / 'lib'
dri = base / 'dri'
lib.mkdir(parents=True, exist_ok=True)
dri.mkdir(parents=True, exist_ok=True)
sources = [
    '/usr/lib/riscv64-linux-gnu/libEGL_mesa.so.0',
    '/usr/lib/riscv64-linux-gnu/libgbm.so.1',
    '/usr/lib/riscv64-linux-gnu/libglapi.so.0',
    '/usr/lib/libGLESv2.so.2',
    '/usr/lib/libGLESv1_CM.so.1',
]
package_files = subprocess.check_output(['dpkg', '-L', 'img-pvr-rogue'], text=True).splitlines()
sources.extend(p for p in package_files if p.startswith('/usr/lib/') and '.so' in Path(p).name
               and not Path(p).name.startswith('libvulkan.so') and Path(p).is_file())
for source in sources:
    shutil.copy2(source, lib / Path(source).name)
shutil.copy2('/usr/lib/riscv64-linux-gnu/dri/pvr_dri.so', dri / 'pvr_dri.so')
(base / '50_vf2.json').write_text(json.dumps({
    'file_format_version': '1.0.0',
    'ICD': {'library_path': '/opt/vf2-gpu/lib/libEGL_mesa.so.0'},
}, indent=2) + '\n')
shutil.copy2('/home/user/Documents/plasma-port/gpu-probe', base / 'gpu-probe')

# These versioned dependencies belong to the old monolithic DRI module.
# Keep them in its own compatibility directory; retain the new libc/toolchain.
for pattern in ('libLLVM-15.so.1', 'libicuuc.so.72', 'libicudata.so.72', 'libxml2.so.2',
                'libdrm_radeon.so.1', 'libdrm_nouveau.so.2', 'libxcb-dri2.so.0'):
    source = Path('/usr/lib/riscv64-linux-gnu') / pattern
    if source.exists():
        shutil.copy2(source, lib / source.name)

# Keep the GLVND dispatch libraries matched to the legacy EGL vendor. Mixing
# newer dispatch wrappers with this driver made libepoxy report no GL context.
for name in ('libGLdispatch.so.0', 'libGL.so.1', 'libOpenGL.so.0', 'libEGL.so.1',
             'libGLX.so.0', 'libGLESv2.so.2'):
    shutil.copy2(Path('/usr/lib/riscv64-linux-gnu') / name, lib / name)
print('Vendor GPU copied to', base)
