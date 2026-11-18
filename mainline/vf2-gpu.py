#!/usr/bin/env python3
"""Enable the JH7110 PowerVR BXE-4-32 GPU on mainline. Run from the kernel tree root.

The open drm/imagination driver manages at most three clocks and one reset.
The JH7110 GPU also needs its APB, RTC, bus and AXI clocks and a second reset,
so a simple-pm-bus parent turns on the extra clocks, and the driver takes its
resets as an array.
"""
import sys
from pathlib import Path


def patch(path, old, new):
    p = Path(path)
    s = p.read_text()
    if new in s:
        return
    if s.count(old) != 1:
        sys.exit(f"vf2-gpu: {path}: anchor not found, upstream changed")
    p.write_text(s.replace(old, new))
    print(f"vf2-gpu: patched {path}")


patch("drivers/gpu/drm/imagination/pvr_power.c",
      "reset = devm_reset_control_get_optional_exclusive(drm_dev->dev, NULL);",
      "reset = devm_reset_control_array_get_optional_exclusive(drm_dev->dev);")

dts = Path("arch/riscv/boot/dts/starfive/jh7110-starfive-visionfive-2-v1.3b.dts")
node = """
/* PowerVR BXE-4-32 for drm/imagination (firmware powervr/rogue_36.50.54.182_v1.fw). */
&{/soc} {
	gpu_bus: bus@18000000 {
		compatible = "simple-pm-bus";
		#address-cells = <2>;
		#size-cells = <2>;
		ranges;
		clocks = <&syscrg JH7110_SYSCLK_GPU_APB>,
			 <&syscrg JH7110_SYSCLK_GPU_RTC_TOGGLE>,
			 <&syscrg JH7110_SYSCLK_GPU_CORE>,
			 <&syscrg JH7110_SYSCLK_NOC_BUS_GPU_AXI>;
		power-domains = <&pwrc JH7110_PD_GPUA>;

		gpu: gpu@18000000 {
			compatible = "starfive,jh7110-gpu", "img,img-bxe-4-32", "img,img-rogue";
			reg = <0x0 0x18000000 0x0 0x100000>;
			interrupts = <82>;
			clocks = <&syscrg JH7110_SYSCLK_GPU_CORE_CLK>,
				 <&syscrg JH7110_SYSCLK_NOC_BUS_GPU_AXI>,
				 <&syscrg JH7110_SYSCLK_GPU_SYS_CLK>;
			clock-names = "core", "mem", "sys";
			resets = <&syscrg JH7110_SYSRST_GPU_APB>,
				 <&syscrg JH7110_SYSRST_GPU_DOMA>;
			power-domains = <&pwrc JH7110_PD_GPUA>;
		};
	};
};
"""
s = dts.read_text()
if "gpu_bus: bus@18000000" not in s:
    dts.write_text(s.rstrip("\n") + "\n" + node)
    print(f"vf2-gpu: added GPU node to {dts}")
