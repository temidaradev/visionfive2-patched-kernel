#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>

int main(void)
{
    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) { perror("open"); return 1; }
    volatile uint32_t *r = mmap(NULL, 4096, PROT_READ | PROT_WRITE,
                                MAP_SHARED, fd, 0x295d0000);
    if (r == MAP_FAILED) { perror("mmap"); return 1; }
    uint32_t old = r[0xdc / 4];
    /* Use a 32-bit peripheral access, never byte writes to MMIO. */
    r[0xdc / 4] = (19u << 17) | 1418u;
    __sync_synchronize();
    printf("DPHY_TIME %08x -> %08x\n", old, r[0xdc / 4]);
    munmap((void *)r, 4096);
    close(fd);
    return 0;
}
