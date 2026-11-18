/* Temporary Cadence hardware test pattern; restores the original registers. */
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
    unsigned offsets[] = {4, 0xfc, 0x100, 0x104, 0x108, 0x10c, 0x110};
    uint32_t saved[7];
    for (unsigned i=0; i<7; i++) saved[i] = r[offsets[i]/4];
    r[4/4] = saved[0] & ~(1u<<5);
    r[0xfc/4] = 0;
    r[0x100/4] = (1280u<<16) | 2160u;
    r[0x104/4] = 0xfff;
    r[0x108/4] = 0;
    r[0x10c/4] = 0;
    r[0x110/4] = 0xfff;
    r[4/4] = saved[0] | (1u<<6);
    r[0xfc/4] = (120u<<5) | (2u<<3) | 1u;
    __sync_synchronize();
    usleep(500000);
    printf("TVG status=%08x, video status=%08x, lane=%08x. Enter restores.\n",
           r[0x114/4], r[0xf0/4], r[0x2c/4]);
    fflush(stdout);
    getchar();
    r[0xfc/4] = 4;
    r[4/4] = saved[0] & ~(1u<<5);
    for (unsigned i=2; i<7; i++) r[offsets[i]/4] = saved[i];
    r[0xfc/4] = saved[1];
    r[4/4] = saved[0];
    __sync_synchronize();
    munmap((void *)r, 4096);
    close(fd);
}
