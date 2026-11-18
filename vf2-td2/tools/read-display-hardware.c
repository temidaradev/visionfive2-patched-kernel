#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>

static void dump(int fd, unsigned long base, size_t size,
                 const unsigned *offsets, size_t n)
{
    volatile uint32_t *r = mmap(NULL, size, PROT_READ, MAP_SHARED, fd, base);
    if (r == MAP_FAILED) { perror("mmap"); return; }
    for (size_t i = 0; i < n; i++)
        printf("%08lx + %04x: %08x\n", base, offsets[i], r[offsets[i] / 4]);
    munmap((void *)r, size);
}
int main(void)
{
    int fd = open("/dev/mem", O_RDONLY | O_SYNC);
    if (fd < 0) { perror("open"); return 1; }
    unsigned dc[] = {0x141c, 0x1434, 0x143c, 0x1444, 0x144c,
                     0x14bc, 0x1ccc, 0x1cd4, 0x251c};
    unsigned sys[] = {0, 4, 8, 12};
    unsigned dsi[] = {0, 4, 8, 12, 0x24, 0x28, 0x2c, 0xb0, 0xb4,
                      0xc0, 0xc4, 0xdc, 0xe8, 0xec, 0xf0, 0x180, 0x1a8, 0x1ac};
    dump(fd, 0x29400000, 0x3000, dc, sizeof(dc)/sizeof(*dc));
    dump(fd, 0x295b0000, 0x1000, sys, sizeof(sys)/sizeof(*sys));
    dump(fd, 0x295d0000, 0x1000, dsi, sizeof(dsi)/sizeof(*dsi));
    close(fd);
}
