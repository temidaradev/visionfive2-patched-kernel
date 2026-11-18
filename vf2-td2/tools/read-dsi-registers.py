import os
import mmap
import struct

# Read-only inspection of the documented Cadence DSI MMIO resource.
fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
with mmap.mmap(fd, 4096, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ,
               offset=0x295d0000) as regs:
    for offset, name in [(4, 'DATA_CTL'), (8, 'PHY_CTL'), (12, 'MAIN_EN'),
                         (0x24, 'MAIN_STS'), (0x28, 'DPHY_ERR'),
                         (0x2c, 'LANE_STS'), (0xb0, 'VID_CTL'),
                         (0xb4, 'VSIZE1'), (0xb8, 'VSIZE2'),
                         (0xc0, 'HSIZE1'), (0xc4, 'HSIZE2'),
                         (0xcc, 'BLKSIZE1'), (0xdc, 'DPHY_TIME'),
                         (0xf0, 'VID_STS'), (0x1a8, 'DPI_STS')]:
        print(f'{name:12s} {offset:#05x}: {struct.unpack_from("<I", regs, offset)[0]:08x}')
os.close(fd)
