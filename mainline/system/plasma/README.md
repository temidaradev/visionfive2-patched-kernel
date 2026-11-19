# KDE Plasma 6 on Wayland with the PowerVR GPU

Plasma 6 is installed into a separate Debian root, `/opt/plasma68-root`. The
board's own userland is too old for Plasma 6. The session runs in a private
mount namespace and uses the StarFive vendor GL stack, which
`prepare-vendor-gpu.py` copies to `/opt/vf2-gpu`.

To make KWin work with the 2023 vendor EGL:

- **Render through `card0`, the display device.** On the render node, the
  vendor EGL marks the RGB formats as external-only, so KWin won't render into
  them.
- **Load `gbm-trace.c` (`libgbm-trace.so`) with `LD_PRELOAD`.** It does three
  things:
  - drops DRM master on the early render file descriptor, so logind can still
    grant KWin the display (`VF2_DROP_RENDER_MASTER`);
  - binds the legacy `wl_drm` interface that vendor EGL clients need
    (`VF2_BIND_WL_DRM`);
  - retries client `drmAuthMagic` calls on KWin's master file descriptor.
- **Set the safe KWin options:** `KWIN_DRM_FORCE_GL_FINISH_*`, no timer queries,
  no persistent VBOs, no buffer age.

Results: KWin composites with OpenGL ES on the PowerVR B-Series BXE-4-32, and
Wayland clients render on the GPU (glmark2 build scene: 866 FPS).

Install:

- `plasma-vf2-wayland` goes in `/usr/local/libexec/`;
- `start-plasma-vf2-wayland` goes in `/usr/local/bin/`;
- the `.desktop` file goes in `/usr/share/wayland-sessions/`.

If Plasma exits within 30 seconds, the launcher falls back to `sway-vf2`.

Most of this work was done by Codex on the board (`~/Documents/plasma-port`).

## Plasma shell on the GPU

Qt 6 on Debian is built for desktop OpenGL, so Qt asks EGL for `EGL_OPENGL_BIT`
configs. The vendor EGL only supports OpenGL ES, so no config matched and Plasma
fell back to software rendering. With `VF2_EGL_FORCE_GLES=1`, `gbm-trace.c`
rewrites those requests to ES configs and binds the ES API instead. Also remove
any `SceneGraphBackend=software` left in `~/.config/plasma-vf2/kdeglobals` by an
earlier fallback.

Result: plasmashell renders on PowerVR and uses about 1% CPU at idle
(previously 30–40% in software).

## Board applications in Plasma's menu

- At every login, `vf2-sync-host-apps` adds the board's installed applications
  to Plasma's menu, in `~/.local/share/plasma-vf2/applications/host-*`.
- Each entry runs through `vf2-host-run`, inside the Plasma root. It starts
  `vf2-host-app` on the board as a transient unit of the user's systemd
  manager, connected to the Plasma Wayland session.
- The board's icon themes are shared read-only into the Plasma root at
  `/opt/host-share`.

Install `vf2-sync-host-apps` to `/usr/local/libexec/`, `vf2-host-app` to the
board's `/usr/local/bin/`, and `vf2-host-run` to
`/opt/plasma68-root/usr/local/bin/`.
