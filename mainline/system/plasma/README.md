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
