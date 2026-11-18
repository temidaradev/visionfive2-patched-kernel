#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>
int main(void) {
 int fd=open("/dev/mem",O_RDWR|O_SYNC);
 if(fd<0)return 1;
 volatile uint32_t *dc=mmap(NULL,0x3000,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0x29400000);
 volatile uint32_t *dsi=mmap(NULL,0x1000,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0x295d0000);
 if(dc==MAP_FAILED||dsi==MAP_FAILED)return 1;
 uint32_t data=dsi[1],en=dsi[3];
 for(unsigned i=0;i<1;i++) {
  dsi[1]=data&~(1u<<5); dsi[3]=en&~(1u<<14); usleep(50000);
  dc[0x143c/4]=0x41a0033e|((i&1)?0x80000000:0);
  dc[0x144c/4]=0x42db05b4|((i&2)?0x80000000:0);
  __sync_synchronize();
  dsi[3]=en; dsi[1]=data; dsi[0x160/4]=0x7fe;
  sleep(5);
  printf("polarity %u H=%08x V=%08x status=%08x flag=%08x fifo=%08x\n",i,dc[0x143c/4],dc[0x144c/4],dsi[0xf0/4],dsi[0x180/4],dsi[0x1ac/4]); fflush(stdout);
 }
 close(fd);
}
