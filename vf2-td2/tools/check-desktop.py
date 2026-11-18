from pathlib import Path
import os, pwd, subprocess
for pid in subprocess.check_output(['pgrep', '-x', 'gnome-shell'], text=True).split():
    proc = Path('/proc') / pid
    uid = proc.stat().st_uid
    user = pwd.getpwuid(uid).pw_name
    env = dict(s.split('=', 1) for s in (proc/'environ').read_text().split('\0') if '=' in s)
    print('GNOME session:', user, pid, flush=True)
    cmd = ['sudo', '-u', user, 'env', 'DBUS_SESSION_BUS_ADDRESS=' + env['DBUS_SESSION_BUS_ADDRESS'],
           'gdbus', 'call', '--session', '--dest', 'org.gnome.Mutter.DisplayConfig',
           '--object-path', '/org/gnome/Mutter/DisplayConfig',
           '--method', 'org.gnome.Mutter.DisplayConfig.GetCurrentState']
    try:
        subprocess.run(cmd, timeout=15)
    except subprocess.TimeoutExpired:
        print('DisplayConfig query timed out')
    libraries = sorted(set(l.split()[-1] for l in (proc/'maps').read_text().splitlines()
                           if any(x in l.lower() for x in ['dri.so', 'pvr', 'swrast'])))
    print('Rendering libraries:', '\n'.join(libraries), flush=True)
