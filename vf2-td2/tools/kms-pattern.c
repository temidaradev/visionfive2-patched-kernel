#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <drm.h>
#include <drm_mode.h>

int main(void)
{
    int fd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    if (fd < 0) { perror("open"); return 1; }
    if (drmSetMaster(fd)) { perror("drmSetMaster"); return 1; }
    drmModeRes *res = drmModeGetResources(fd);
    drmModeConnector *conn = NULL;
    for (int i = 0; res && i < res->count_connectors; i++) {
        drmModeConnector *c = drmModeGetConnector(fd, res->connectors[i]);
        if (c && c->connector_type == DRM_MODE_CONNECTOR_DSI && c->count_modes) {
            conn = c;
            break;
        }
        drmModeFreeConnector(c);
    }
    if (!conn || res->count_crtcs < 2) { fprintf(stderr, "No DSI mode/CRTC\n"); return 1; }
    drmModeModeInfo mode = conn->modes[0];
    struct drm_mode_create_dumb dumb = { .width = mode.hdisplay,
        .height = mode.vdisplay, .bpp = 32 };
    if (drmIoctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &dumb)) { perror("create dumb"); return 1; }
    uint32_t fb;
    if (drmModeAddFB(fd, dumb.width, dumb.height, 24, 32, dumb.pitch, dumb.handle, &fb)) {
        perror("add fb"); return 1;
    }
    struct drm_mode_map_dumb map = { .handle = dumb.handle };
    if (drmIoctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &map)) { perror("map dumb"); return 1; }
    void *mem = mmap(NULL, dumb.size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, map.offset);
    if (mem == MAP_FAILED) { perror("mmap"); return 1; }
    uint32_t colors[] = {0xff0000, 0x00ff00, 0x0000ff, 0xffffff, 0xffff00, 0x00ffff};
    for (unsigned y = 0; y < dumb.height; y++) {
        uint32_t *row = (uint32_t *)((char *)mem + y * dumb.pitch);
        for (unsigned x = 0; x < dumb.width; x++)
            row[x] = colors[x * 6 / dumb.width];
    }
    uint32_t crtc = res->crtcs[1];
    if (drmModeSetCrtc(fd, crtc, fb, 0, 0, &conn->connector_id, 1, &mode)) {
        perror("set crtc"); return 1;
    }
    printf("Color bars: connector %u CRTC %u %ux%u; press Enter to release.\n",
           conn->connector_id, crtc, dumb.width, dumb.height);
    fflush(stdout);
    getchar();
    drmDropMaster(fd);
    close(fd);
    return 0;
}
