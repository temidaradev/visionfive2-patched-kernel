#!/usr/bin/python3
from gi.repository import Gio, GLib
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
name = 'org.gnome.Mutter.DisplayConfig'
path = '/org/gnome/Mutter/DisplayConfig'
state = bus.call_sync(name, path, name, 'GetCurrentState', None, None,
                      Gio.DBusCallFlags.NONE, -1, None).unpack()
serial, monitors, logical, props = state
panel = next(m for m in monitors if m[0][0] == 'DSI-1')
mode = next(m[0] for m in panel[1] if m[6].get('is-preferred'))
args = GLib.Variant('(uua(iiduba(ssa{sv}))a{sv})',
                    (serial, 1, [(0, 0, 1.0, 1, True,
                                 [('DSI-1', mode, {})])], {}))
bus.call_sync(name, path, name, 'ApplyMonitorsConfig', args, None,
              Gio.DBusCallFlags.NONE, -1, None)
print('Applied landscape 1280x720 at scale 1')
