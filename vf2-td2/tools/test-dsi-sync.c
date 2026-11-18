#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>
int main(void) {
    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) { perror("open"); return 1; }
    volatile uint32_t *dc = mmap(NULL, 0x3000, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0x29400000);
    volatile uint32_t *dsi = mmap(NULL, 0x1000, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0x295d0000);
    if (dc == MAP_FAILED || dsi == MAP_FAILED) return 1;
    uint32_t h = dc[0x143c/4], v = dc[0x144c/4];
    printf("before H=%08x V=%08x\n", h, v);
    /* Restore the mode's actual two-line pulse. */
    dc[0x144c/4] = (v & 0xc0000000) | (1462u << 15) | 1460u;
    __sync_synchronize();
    dsi[0x160/4] = 0xffffffff;
    sleep(2);
    printf("pulse restored: status=%08x flags=%08x\n", dsi[0xf0/4], dsi[0x180/4]);
    /* Cadence's DPI input uses positive sync pulses. */
    dc[0x143c/4] = h & ~(1u << 31);
    dc[0x144c/4] &= ~(1u << 31);
    __sync_synchronize();
    dsi[0x160/4] = 0xffffffff;
    sleep(2);
    printf("positive sync: H=%08x V=%08x status=%08x flags=%08x\n", dc[0x143c/4], dc[0x144c/4], dsi[0xf0/4], dsi[0x180/4]);
    munmap((void *)dc, 0x3000); munmap((void *)dsi, 0x1000); close(fd);
}
