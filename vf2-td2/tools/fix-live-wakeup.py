"""Correct the confirmed ps/ns error in the active diagnostic DSI timing."""
import mmap
import os
import struct
fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
with mmap.mmap(fd, 4096, flags=mmap.MAP_SHARED,
               prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=0x295d0000) as regs:
    old = struct.unpack_from('<I', regs, 0xdc)[0]
    assert old & 0x1ffff == 1418, hex(old)
    # phy timing = 40 ns + 4 UI + 105 ns + 6 UI. At 960 Mbps,
    # the byte clock is 120 MHz, yielding ceil(18.65) = 19 cycles.
    value = (19 << 17) | (old & 0x1ffff)
    struct.pack_into('<I', regs, 0xdc, value)
    print(f'DPHY wakeup: {old:08x} -> {struct.unpack_from("<I", regs, 0xdc)[0]:08x}')
os.close(fd)
