/* Follow Cadence's startup requirement: arm DSI before starting the DPI source. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>
int main(void) {
 int fd=open("/dev/mem",O_RDWR|O_SYNC); if(fd<0)return 1;
 volatile uint32_t *dc=mmap(NULL,0x3000,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0x29400000);
 volatile uint32_t *dsi=mmap(NULL,0x1000,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0x295d0000);
 if(dc==MAP_FAILED||dsi==MAP_FAILED)return 1;
 uint32_t start=dc[0x1ccc/4], data=dsi[1], en=dsi[3];
 dc[0x1ccc/4]=start&~2u; __sync_synchronize(); usleep(50000);
 dsi[1]=data&~(1u<<5); dsi[3]=en&~(1u<<14); usleep(50000);
 dc[0x143c/4]=0x41a0033e;
 dc[0x144c/4]=0x42db05b4;
 dsi[0xdc/4]=(141u<<17)|1418u;
 dsi[3]=en; dsi[1]=data; __sync_synchronize();
 dc[0x1ccc/4]=start;
 dsi[0x160/4]=0x7fe;
 for(int i=0;i<3;i++) {
  sleep(3);
  printf("%ds status=%08x flag=%08x fifo=%08x vpos=%08x\n",(i+1)*3,dsi[0xf0/4],dsi[0x180/4],dsi[0x1ac/4],dsi[0xe8/4]); fflush(stdout);
 }
 close(fd);
}
