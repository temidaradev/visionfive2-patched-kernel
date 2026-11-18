import fcntl, os, select, struct, time
fd = os.open('/dev/input/event4', os.O_RDONLY | os.O_NONBLOCK)
for code in (0, 1, 53, 54):
    buf = bytearray(24)
    fcntl.ioctl(fd, 0x80184540 + code, buf)
    print('axis', code, struct.unpack('6i', buf), flush=True)
end = time.monotonic() + 35
n = 0
while time.monotonic() < end:
    if not select.select([fd], [], [], 1)[0]:
        continue
    raw = os.read(fd, 24 * 64)
    for t, us, kind, code, value in struct.iter_unpack('llHHi', raw):
        n += 1
        if kind in (1, 3):
            print(kind, code, value, flush=True)
print('Total events:', n, flush=True)
