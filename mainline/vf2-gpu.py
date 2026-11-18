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

patch("drivers/pmdomain/starfive/jh71xx-pmu.c",
      "\tpmu->base = devm_platform_ioremap_resource(pdev, 0);\n\tif (IS_ERR(pmu->base))\n\t\treturn PTR_ERR(pmu->base);\n",
      "\tpmu->base = devm_platform_ioremap_resource(pdev, 0);\n\tif (IS_ERR(pmu->base))\n\t\treturn PTR_ERR(pmu->base);\n"
      "\t/* Vendor GPU bring-up: stop hardware events from powering domains off behind software. */\n"
      "\twritel(0, pmu->base + 0x08);\n")


# --- Cache coherency: the JH7110 GPU doesn't snoop the CPU's L2, and the U74 cores
# can't map memory uncached (no Svpbmt), so the write-combined mappings
# drm/imagination relies on are really cached. Mark the GPU dma-noncoherent (so DMA
# syncs use the SiFive ccache flush ops) and write back / invalidate all firmware
# objects at every CPU<->firmware handoff, as StarFive's vendor DDK does.
patch("drivers/gpu/drm/imagination/pvr_fw.h",
      "#endif /* PVR_FW_H */",
      "void pvr_fw_object_sync(struct pvr_device *pvr_dev, struct pvr_fw_object *fw_obj,\n"
      "\t\t\tbool for_device);\n"
      "void pvr_fw_sync_all_objs(struct pvr_device *pvr_dev, bool for_device);\n\n"
      "#endif /* PVR_FW_H */")

FW_HELPERS = """
/* VisionFive 2 (JH7110): explicit cache maintenance for a non-coherent GPU. */
void
pvr_fw_object_sync(struct pvr_device *pvr_dev, struct pvr_fw_object *fw_obj, bool for_device)
{
	struct device *dev = from_pvr_device(pvr_dev)->dev;
	struct drm_gem_shmem_object *shmem;

	if (!fw_obj || device_get_dma_attr(dev) == DEV_DMA_COHERENT)
		return;
	shmem = shmem_gem_from_pvr_gem(fw_obj->gem);
	if (!shmem->sgt)
		return;
	if (for_device)
		dma_sync_sgtable_for_device(dev, shmem->sgt, DMA_BIDIRECTIONAL);
	else
		dma_sync_sgtable_for_cpu(dev, shmem->sgt, DMA_BIDIRECTIONAL);
}

void
pvr_fw_sync_all_objs(struct pvr_device *pvr_dev, bool for_device)
{
	struct pvr_fw_object *fw_obj;

	if (device_get_dma_attr(from_pvr_device(pvr_dev)->dev) == DEV_DMA_COHERENT)
		return;
	mutex_lock(&pvr_dev->fw_dev.fw_objs.lock);
	list_for_each_entry(fw_obj, &pvr_dev->fw_dev.fw_objs.list, node)
		pvr_fw_object_sync(pvr_dev, fw_obj, for_device);
	mutex_unlock(&pvr_dev->fw_dev.fw_objs.lock);
}
"""
p_fw = Path("drivers/gpu/drm/imagination/pvr_fw.c")
t = p_fw.read_text()
if "pvr_fw_sync_all_objs(struct pvr_device *pvr_dev, bool for_device)\n{" not in t:
    t = t.replace("#include <linux/clk.h>\n", "#include <linux/clk.h>\n#include <linux/dma-mapping.h>\n#include <linux/property.h>\n", 1)
    t = t.rstrip("\n") + "\n" + FW_HELPERS
    p_fw.write_text(t)
    print("vf2-gpu: added FW cache-sync helpers")

# Boot: write everything back before starting the FW; invalidate while polling for it.
patch("drivers/gpu/drm/imagination/pvr_fw.c",
      "\twhile (ktime_to_ns(ktime_sub(deadline, ktime_get())) > 0) {\n\t\tif (READ_ONCE(fw_dev->fwif_sysinit->firmware_started))",
      "\twhile (ktime_to_ns(ktime_sub(deadline, ktime_get())) > 0) {\n\t\tpvr_fw_object_sync(pvr_dev, fw_dev->mem.sysinit_obj, false);\n\t\tif (READ_ONCE(fw_dev->fwif_sysinit->firmware_started))")
patch("drivers/gpu/drm/imagination/pvr_fw.c",
      "\terr = pvr_fw_start(pvr_dev);",
      "\tpvr_fw_sync_all_objs(pvr_dev, true);\n\terr = pvr_fw_start(pvr_dev);")
# Every kick to the FW: write back all FW objects first.
patch("drivers/gpu/drm/imagination/pvr_fw.c",
      "pvr_fw_mts_schedule(struct pvr_device *pvr_dev, u32 val)\n{\n",
      "pvr_fw_mts_schedule(struct pvr_device *pvr_dev, u32 val)\n{\n\tpvr_fw_sync_all_objs(pvr_dev, true);\n")
# KCCB return slots are written by the FW: invalidate before each read.
patch("drivers/gpu/drm/imagination/pvr_ccb.c",
      "\tint ret = wait_event_timeout(pvr_dev->kccb.rtn_q, READ_ONCE(pvr_dev->kccb.rtn[slot_nr]) &",
      "\tint ret = wait_event_timeout(pvr_dev->kccb.rtn_q,\n\t\t(pvr_fw_object_sync(pvr_dev, pvr_dev->kccb.rtn_obj, false),\n\t\t READ_ONCE(pvr_dev->kccb.rtn[slot_nr])) &")
patch("drivers/gpu/drm/imagination/pvr_ccb.c",
      "\tif (ret && rtn_out)\n\t\t*rtn_out = READ_ONCE(pvr_dev->kccb.rtn[slot_nr]);",
      "\tif (ret && rtn_out) {\n\t\tpvr_fw_object_sync(pvr_dev, pvr_dev->kccb.rtn_obj, false);\n\t\t*rtn_out = READ_ONCE(pvr_dev->kccb.rtn[slot_nr]);\n\t}")
# FW -> CPU messages, KCCB read offsets and job-completion UFOs: invalidate on every IRQ.
patch("drivers/gpu/drm/imagination/pvr_device.c",
      "\t\tif (READ_ONCE(pvr_dev->fw_dev.initialised)) {\n\t\t\tpvr_fwccb_process(pvr_dev);",
      "\t\tif (READ_ONCE(pvr_dev->fw_dev.initialised)) {\n\t\t\tpvr_fw_sync_all_objs(pvr_dev, false);\n\t\t\tpvr_fwccb_process(pvr_dev);")


# --- User buffers (command streams, vertex data, textures, results) are mapped
# write-combined by Mesa, which is really cached here as well. Write back and
# invalidate every BO in the job's VM at submit, before the GPU can see it.
# Done before drm_exec takes the reservation locks to keep vm_ctx->lock ordering.
patch("drivers/gpu/drm/imagination/pvr_vm.h",
      "#endif /* PVR_VM_H */",
      "void pvr_vm_sync_for_device(struct pvr_vm_context *vm_ctx);\n\n#endif /* PVR_VM_H */")
VM_SYNC = """
/* VisionFive 2 (JH7110): non-coherent GPU, see pvr_fw_sync_all_objs(). */
void
pvr_vm_sync_for_device(struct pvr_vm_context *vm_ctx)
{
	struct device *dev = from_pvr_device(vm_ctx->pvr_dev)->dev;
	struct drm_gpuva *va;

	if (device_get_dma_attr(dev) == DEV_DMA_COHERENT)
		return;
	mutex_lock(&vm_ctx->lock);
	drm_gpuvm_for_each_va(va, &vm_ctx->gpuvm_mgr) {
		struct drm_gem_shmem_object *shmem;

		if (!va->gem.obj)
			continue;
		shmem = to_drm_gem_shmem_obj(va->gem.obj);
		if (shmem->sgt)
			dma_sync_sgtable_for_device(dev, shmem->sgt, DMA_BIDIRECTIONAL);
	}
	mutex_unlock(&vm_ctx->lock);
}
"""
p_vm = Path("drivers/gpu/drm/imagination/pvr_vm.c")
t = p_vm.read_text()
if "pvr_vm_sync_for_device(struct pvr_vm_context *vm_ctx)\n{" not in t:
    t = t.replace("#include <linux/bug.h>\n", "#include <linux/bug.h>\n#include <linux/dma-mapping.h>\n#include <linux/property.h>\n", 1)
    p_vm.write_text(t.rstrip("\n") + "\n" + VM_SYNC)
    print("vf2-gpu: added pvr_vm_sync_for_device")
patch("drivers/gpu/drm/imagination/pvr_job.c",
      '#include "pvr_stream_defs.h"\n',
      '#include "pvr_stream_defs.h"\n#include "pvr_vm.h"\n')
patch("drivers/gpu/drm/imagination/pvr_job.c",
      "\tdrm_exec_init(&exec, DRM_EXEC_INTERRUPTIBLE_WAIT | DRM_EXEC_IGNORE_DUPLICATES, 0);\n",
      "\tfor (u32 i = 0; i < args->jobs.count; i++) {\n"
      "\t\tif (!i || job_data[i].job->ctx->vm_ctx != job_data[i - 1].job->ctx->vm_ctx)\n"
      "\t\t\tpvr_vm_sync_for_device(job_data[i].job->ctx->vm_ctx);\n"
      "\t}\n\n"
      "\tdrm_exec_init(&exec, DRM_EXEC_INTERRUPTIBLE_WAIT | DRM_EXEC_IGNORE_DUPLICATES, 0);\n")

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
		/* The vendor driver's 594 MHz core clock (1.5 GHz speed bin). */
		assigned-clocks = <&syscrg JH7110_SYSCLK_GPU_CORE>;
		assigned-clock-rates = <594000000>;

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
			/* The GPU does not snoop the CPU caches. */
			dma-noncoherent;
		};
	};
};
"""
s = dts.read_text()
if "gpu_bus: bus@18000000" not in s:
    dts.write_text(s.rstrip("\n") + "\n" + node)
    print(f"vf2-gpu: added GPU node to {dts}")
