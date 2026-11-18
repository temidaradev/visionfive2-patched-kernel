#!/bin/bash
set -euo pipefail
src=/home/user/vf2-sdk/linux
out=/home/user/td2-touch-module
mkdir -p "$out"
cp "$src/drivers/input/touchscreen/goodix.h" "$out/"
cp "$src/drivers/input/touchscreen/goodix_fwupload.c" "$out/"
cp /home/user/td2-drm-module/goodix-rpi-6.12.c "$out/goodix.c"
python3 - <<'PY'
from pathlib import Path
p=Path('/home/user/td2-touch-module/goodix.c')
s=p.read_text().replace('.name = "Goodix-TS",', '.name = "td2-goodix-poll",')
marker='\tdev_dbg(&client->dev, "I2C Address: 0x%02x\\n", client->addr);'
assert s.count(marker)==1
s=s.replace(marker, marker + '''
	/* Touch Display 2 carries I2C, but no Goodix interrupt over the ribbon. */
	client->irq = 0;
''')
p.write_text(s)
PY
cat > "$out/Makefile" <<'MAKE'
obj-m := td2_touch.o
td2_touch-y := goodix.o goodix_fwupload.o
MAKE
make -C "$src" M="$out" -j3 modules
/sbin/modinfo "$out/td2_touch.ko"
