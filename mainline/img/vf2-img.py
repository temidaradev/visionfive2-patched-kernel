#!/usr/bin/env python3
"""Kernel-side support for StarFive's vendor PowerVR driver (img-rogue) on mainline.
Run from the kernel tree root after drivers/gpu/drm/img has been copied in."""
import sys
from pathlib import Path

def patch(path, old, new, count=1):
    p = Path(path); s = p.read_text()
    if new in s:
        return
    if s.count(old) != 1:
        sys.exit(f"vf2-img: {path}: anchor not found, upstream changed")
    p.write_text(s.replace(old, new, count)); print(f"vf2-img: patched {path}")

# Build hooks.
patch("drivers/gpu/drm/Kconfig", 'source "drivers/gpu/drm/imagination/Kconfig"\n',
      'source "drivers/gpu/drm/imagination/Kconfig"\n\nsource "drivers/gpu/drm/img/Kconfig"\n')
patch("drivers/gpu/drm/Makefile", "obj-$(CONFIG_DRM_POWERVR) += imagination/\n",
      "obj-$(CONFIG_DRM_POWERVR) += imagination/\nobj-$(CONFIG_DRM_IMG) += img/\n")

# The vendor driver masks PMU hardware events before powering the GPU.
h = Path("include/soc/starfive/jh7110_pmu.h")
if not h.exists():
    h.parent.mkdir(parents=True, exist_ok=True)
    h.write_text("""/* SPDX-License-Identifier: GPL-2.0 */
/* StarFive JH7110 PMU hardware events (vendor GPU driver interface). */
#ifndef __SOC_STARFIVE_JH7110_PMU_H__
#define __SOC_STARFIVE_JH7110_PMU_H__

#include <linux/bits.h>
#include <linux/types.h>

enum PMU_HARD_EVENT {
	PMU_HW_EVENT_RTC	= BIT(0),
	PMU_HW_EVENT_GMAC	= BIT(1),
	PMU_HW_EVENT_RFU	= BIT(2),
	PMU_HW_EVENT_RGPIO0	= BIT(3),
	PMU_HW_EVENT_RGPIO1	= BIT(4),
	PMU_HW_EVENT_RGPIO2	= BIT(5),
	PMU_HW_EVENT_RGPIO3	= BIT(6),
	PMU_HW_EVENT_GPU	= BIT(7),
	PMU_HW_EVENT_ALL	= GENMASK(7, 0),
};

void starfive_pmu_hw_event_turn_off_mask(u32 mask);

#endif /* __SOC_STARFIVE_JH7110_PMU_H__ */
""")
    print(f"vf2-img: added {h}")

pmu = "drivers/pmdomain/starfive/jh71xx-pmu.c"
patch(pmu, "#define JH71XX_PMU_SW_TURN_ON_POWER\t0x0C\n",
      "#define JH71XX_PMU_HW_EVENT_TURN_OFF\t0x08\n#define JH71XX_PMU_SW_TURN_ON_POWER\t0x0C\n")
patch(pmu, "static int jh71xx_pmu_get_state(",
      "static void __iomem *jh71xx_pmu_base;\n\n"
      "/* Used by the vendor PowerVR driver (img-rogue) around GPU power-up. */\n"
      "void starfive_pmu_hw_event_turn_off_mask(u32 mask)\n{\n"
      "\tif (jh71xx_pmu_base)\n\t\twritel(mask, jh71xx_pmu_base + JH71XX_PMU_HW_EVENT_TURN_OFF);\n}\n"
      "EXPORT_SYMBOL_GPL(starfive_pmu_hw_event_turn_off_mask);\n\n"
      "static int jh71xx_pmu_get_state(")
patch(pmu, "\tpmu->base = devm_platform_ioremap_resource(pdev, 0);\n\tif (IS_ERR(pmu->base))\n\t\treturn PTR_ERR(pmu->base);\n",
      "\tpmu->base = devm_platform_ioremap_resource(pdev, 0);\n\tif (IS_ERR(pmu->base))\n\t\treturn PTR_ERR(pmu->base);\n\tjh71xx_pmu_base = pmu->base;\n")

# Device tree: the vendor driver's GPU node (from StarFive's jh7110.dtsi), enabled.
dts = Path("arch/riscv/boot/dts/starfive/jh7110-starfive-visionfive-2-v1.3b.dts")
s = dts.read_text()
if '"img-gpu"' not in s:
    dts.write_text(s.rstrip("\n") + """

/* PowerVR BXE-4-32 for StarFive's vendor driver (img-rogue, DDK 1.19). */
&{/soc} {
	gpu: gpu@18000000 {
		compatible = "img-gpu";
		reg = <0x0 0x18000000 0x0 0x100000>,
		      <0x0 0x130c000 0x0 0x10000>;
		clocks = <&syscrg JH7110_SYSCLK_GPU_CORE>,
			 <&syscrg JH7110_SYSCLK_GPU_APB>,
			 <&syscrg JH7110_SYSCLK_GPU_RTC_TOGGLE>,
			 <&syscrg JH7110_SYSCLK_GPU_CORE_CLK>,
			 <&syscrg JH7110_SYSCLK_GPU_SYS_CLK>,
			 <&syscrg JH7110_SYSCLK_NOC_BUS_GPU_AXI>;
		clock-names = "clk_bv", "clk_apb", "clk_rtc",
			      "clk_core", "clk_sys", "clk_axi";
		resets = <&syscrg JH7110_SYSRST_GPU_APB>,
			 <&syscrg JH7110_SYSRST_GPU_DOMA>;
		reset-names = "rst_apb", "rst_doma";
		power-domains = <&pwrc JH7110_PD_GPUA>;
		interrupts = <82>;
		current-clock = <8000000>;
	};
};
""")
    print(f"vf2-img: added vendor GPU node to {dts}")

# The vendor driver flushes the SiFive L2 explicitly (the GPU isn't coherent).
# Mainline has the same operation as ccache_flush_range(); export it under the
# vendor name.
cc = "drivers/cache/sifive_ccache.c"
patch(cc, "static const struct riscv_nonstd_cache_ops ccache_mgmt_ops __initconst = {",
      "/* Used by StarFive's vendor PowerVR driver (img-rogue). */\n"
      "void sifive_l2_flush64_range(phys_addr_t start, size_t len)\n{\n"
      "\tccache_flush_range(start, len);\n}\n"
      "EXPORT_SYMBOL_GPL(sifive_l2_flush64_range);\n\n"
      "static const struct riscv_nonstd_cache_ops ccache_mgmt_ops __initconst = {")

# StarFive's closed GL userspace (libpvr_dri_support, DDK 1.19) pairs the PowerVR
# render node only with a display DRM driver named "starfive" (the vendor display
# driver's name). Register mainline's DC8200 driver under that name so the
# compositor gets GPU acceleration; the platform driver stays "verisilicon-dc".
patch("drivers/gpu/drm/verisilicon/vs_drm.c", '#define DRIVER_NAME\t"verisilicon"\n',
      '#define DRIVER_NAME\t"starfive"\t/* vendor GL userspace matches this name */\n')
