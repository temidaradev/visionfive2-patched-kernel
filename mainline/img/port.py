#!/usr/bin/env python3
"""Port StarFive's vendor PowerVR driver (img-rogue, DDK 1.19, from the 6.12 BSP) to Linux 7.4.
Usage: port.py <dir containing drivers/gpu/drm/img>"""
import re, sys
from pathlib import Path
L = Path(sys.argv[1]) / "drivers/gpu/drm/img/img-rogue/services/server/env/linux"

def edit(name, fn):
    p = L / name; s = p.read_text(); n = fn(s)
    if n != s: p.write_text(n); print("ported", name)

# 6.10: __assign_str() takes only the field (source comes from __string()).
def assign_str(s):
    out, i = [], 0
    while True:
        j = s.find("__assign_str(", i)
        if j < 0:
            return "".join(out) + s[i:]
        k = j + len("__assign_str("); depth = 1; m = k
        while depth:
            depth += {"(": 1, ")": -1}.get(s[m], 0); m += 1
        args = s[k:m - 1]
        field = args.split(",", 1)[0].strip()
        out.append(s[i:j] + f"__assign_str({field});")
        i = m
        while i < len(s) and s[i] in " \t": i += 1
        if i < len(s) and s[i] == ";": i += 1
for f in ("pvr_fence_trace.h", "rogue_trace_events.h"):
    edit(f, assign_str)

# 6.17: pfn_t removed; vmf_insert_mixed() takes a plain pfn.
def nopfn(s):
    s = s.replace("#include <linux/pfn_t.h>\n", "")
    s = re.sub(r"\bpfn_t(\s+sPFN)", r"unsigned long\1", s)
    s = re.sub(r"phys_to_pfn_t\(([^,]+),\s*0\)", r"PHYS_PFN(\1)", s)
    s = s.replace("page_to_pfn_t(", "page_to_pfn(").replace("pfn_t_to_page(", "pfn_to_page(")
    s = s.replace("pfn_t_valid(", "pfn_valid(")
    s = re.sub(r"pfn_t_to_pfn\((\w+)\)", r"\1", s)
    return s
edit("pmr_os.c", nopfn); edit("osfunc.c", nopfn)

# 6.14: drm_driver.date removed.
edit("pvr_drm.c", lambda s: s.replace("\t.date\t\t\t= PVR_DRM_DRIVER_DATE,\n", ""))
# 6.13: module namespaces are string literals.
edit("pvr_platform_drv.c", lambda s: s.replace("MODULE_IMPORT_NS(DMA_BUF);", 'MODULE_IMPORT_NS("DMA_BUF");'))

# 6.x: dma_fence_ops lost fence_value_str/timeline_value_str; sw-signaling helper renamed.
for f in ("pvr_fence.c", "pvr_sw_fence.c", "pvr_sync_file.c", "pvr_counting_timeline.c", "pvr_buffer_sync.c"):
    def fence(s):
        s = re.sub(r"\n\s*\.(fence_value_str|timeline_value_str)\s*=\s*\w+,", "", s)
        s = s.replace("dma_fence_enable_sw_signaling(", "dma_fence_enable_signaling(")
        return s
    edit(f, fence)

# 6.16: from_timer() renamed to timer_container_of().
import glob
for p in glob.glob(str(L.parent.parent.parent.parent / "**/*.[ch]"), recursive=True):
    s = Path(p).read_text(errors="replace")
    if "from_timer(" in s:
        Path(p).write_text(s.replace("from_timer(", "timer_container_of(")); print("ported", Path(p).name)

# Vendor code predates newer compiler warnings; keep them as warnings.
mk = Path(sys.argv[1]) / "drivers/gpu/drm/img/img-rogue/Makefile"
s = mk.read_text()
if "-Wno-error" not in s:
    mk.write_text(s + "\n# Linux 7.x: vendor DDK code predates newer warnings.\nccflags-y += -Wno-error\n"); print("ported Makefile (-Wno-error)")

# 6.15: del_timer*() renamed to timer_delete*().
D = Path(sys.argv[1]) / "drivers/gpu/drm/img"
for p in D.rglob("*.[ch]"):
    s = p.read_text(errors="replace")
    n = s.replace("del_timer_sync(", "timer_delete_sync(").replace("del_timer(", "timer_delete(")
    # dma_fence_ops lost fence_value_str/timeline_value_str: format the seqno instead.
    n = re.sub(r"[A-Za-z_]\w*(?:(?:->|\.)\w+)*->(fence|timeline)_value_str(?=\s*[)?])", "true", n)
    n = re.sub(r"[A-Za-z_]\w*(?:(?:->|\.)\w+)*->(fence|timeline)_value_str\(", r"pvr_compat_\1_value_str(", n)
    if "pvr_compat_" in n and p.name != "kernel_compatibility.h" and '#include "kernel_compatibility.h"' not in n:
        n = re.sub(r"(#include [<\"][^\n]+\n)", r'\1#include "kernel_compatibility.h"\n', n, count=1)
    if n != s:
        p.write_text(n); print("ported", p.name)
kc = D / "kernel_compatibility.h"
s = kc.read_text()
if "pvr_compat_fence_value_str" not in s:
    helpers = '''
/* Linux 6.x removed dma_fence_ops.{fence,timeline}_value_str; print the seqno. */
#include <linux/dma-fence.h>
static inline void pvr_compat_fence_value_str(struct dma_fence *f, char *str, int size)
{ snprintf(str, size, "%llu", (unsigned long long)f->seqno); }
static inline void pvr_compat_timeline_value_str(struct dma_fence *f, char *str, int size)
{ snprintf(str, size, "%llu", (unsigned long long)f->seqno); }
'''
    i = s.rfind("#endif")
    kc.write_text(s[:i] + helpers + "\n" + s[i:]); print("ported kernel_compatibility.h")

# Vendor Kbuild adds -Werror per object; newer compilers warn about old code.
kb = D / "img-rogue/services/server/env/linux/Kbuild.mk"
s = kb.read_text()
old = "$(foreach _o,$(addprefix CFLAGS_,$($(PVRSRV_MODNAME)-y)),$(eval $(_o) += -Werror))"
if old in s:
    kb.write_text(s.replace(old, "# Linux 7.x port: no per-object -Werror.\n# " + old)); print("ported Kbuild.mk (-Werror)")

# A comma operator chained into __assign_str(), which is a statement since 6.10.
p = L / "rogue_trace_events.h"; s = p.read_text()
if "__entry->gpu_id = gpu_id,\n" in s:
    p.write_text(s.replace("__entry->gpu_id = gpu_id,\n", "__entry->gpu_id = gpu_id;\n")); print("ported rogue_trace_events.h (comma)")

# kbuild uses .NOTINTERMEDIATE, which can't be combined with .SECONDARY.
mk = Path(sys.argv[1]) / "drivers/gpu/drm/img/img-rogue/Makefile"
s = mk.read_text()
if "\n.SECONDARY:\n" in s:
    mk.write_text(s.replace("\n.SECONDARY:\n", "\n# .SECONDARY: (conflicts with kbuild .NOTINTERMEDIATE)\n")); print("ported Makefile (.SECONDARY)")

# Build pvrsrvkm as a module: a built-in driver probes before the root filesystem
# (and /lib/firmware) is mounted, and mainline boots without an initramfs.
kc = Path(sys.argv[1]) / "drivers/gpu/drm/img/img-rogue/Kconfig"
s = kc.read_text()
if '\tbool "DRM support for PowerVR GPU"' in s:
    kc.write_text(s.replace('\tbool "DRM support for PowerVR GPU"', '\ttristate "DRM support for PowerVR GPU"')); print("ported Kconfig (tristate)")
