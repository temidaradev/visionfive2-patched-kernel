/* Apply the DSI encoder's VOUT mux mask from StarFive's upstream submission. */
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
                                MAP_SHARED, fd, 0x295b0000);
    if (r == MAP_FAILED) { perror("mmap"); return 1; }
    uint32_t old = r[8/4];
    r[8/4] = old | 0x12;
    __sync_synchronize();
    printf("VOUT mux %08x -> %08x\n", old, r[8/4]);
    munmap((void *)r, 4096);
    close(fd);
}
