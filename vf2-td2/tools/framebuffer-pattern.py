import fcntl
import os
import struct

fd = os.open('/dev/fb0', os.O_RDWR)
var, fix = bytearray(160), bytearray(80)
fcntl.ioctl(fd, 0x4600, var, True)  # FBIOGET_VSCREENINFO
fcntl.ioctl(fd, 0x4602, fix, True)  # FBIOGET_FSCREENINFO
w, h = struct.unpack_from('II', var)
bpp = struct.unpack_from('I', var, 24)[0]
stride = struct.unpack_from('I', fix, 48)[0]
assert bpp == 32 and (w, h) == (720, 1280), (w, h, bpp)
assert stride >= w * 4
colors = [0xff0000, 0x00ff00, 0x0000ff, 0xffffff, 0xffff00, 0x00ffff]
row = b''.join(struct.pack('<I', colors[min(x * len(colors) // w, len(colors)-1)])
               for x in range(w))
for y in range(h):
    line = row
    if y < 12 or y >= h-12:
        line = struct.pack('<I', 0xffffff) * w
    os.pwrite(fd, line, y * stride)
os.close(fd)
print(f'Displaying six color bars on {w}x{h}, stride {stride}.')
