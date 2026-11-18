# VisionFive 2 mainline boot (vendor U-Boot 2021.10 runs /boot.scr before extlinux).
#
# 1. One-shot: /boot-once = "1" boots /once.env exactly once. The flag is cleared
#    *before* booting, so any later reset returns to the normal extlinux default.
# 2. Default: if /default.env exists, boot it with a boot counter. /boot-tries counts
#    attempts ("0" -> "1" -> "2"); the board resets it to "0" once the boot is good
#    (vf2-trial-guard). After two failed attempts this script falls through to the
#    extlinux default (vendor 6.12).
# This U-Boot has no `mw`, so counters are advanced by copying one-byte files.
# Each step is logged to /boot/once-log.txt (no serial console needed).
setenv once_dev mmc ${devnum}:${distro_bootpart}
setenv vf2_go 0
setenv once_log ""

if test -e ${once_dev} /boot-once && fatload ${once_dev} ${loadaddr} /boot-once 1 && itest.b *${loadaddr} == 0x31; then
  if fatload ${once_dev} ${loadaddr} /boot-once.clear 1 && fatwrite ${once_dev} ${loadaddr} /boot-once 1; then
    setenv vf2_go 1
    setenv vf2_env /once.env
    setenv once_log "once cleared"
  fi
fi

if test ${vf2_go} = 0 && test -e ${once_dev} /default.env && fatload ${once_dev} ${loadaddr} /boot-tries 1; then
  setenv vf2_next none
  if itest.b *${loadaddr} == 0x30; then
    setenv vf2_next /boot-tries.1
  elif itest.b *${loadaddr} == 0x31; then
    setenv vf2_next /boot-tries.2
  fi
  if test ${vf2_next} = none; then
    setenv once_log "default: 2 failed tries, falling back to extlinux"
  elif fatload ${once_dev} ${loadaddr} ${vf2_next} 1 && fatwrite ${once_dev} ${loadaddr} /boot-tries 1; then
    setenv vf2_go 1
    setenv vf2_env /default.env
    setenv once_log "default try ${vf2_next}"
  fi
fi

if test ${vf2_go} = 1; then
  if fatload ${once_dev} ${loadaddr} ${vf2_env}; then
    env import -t ${loadaddr} ${filesize}
    setenv once_log "${once_log} env"
  fi
  if fatload ${once_dev} ${kernel_addr_r} ${once_kernel}; then
    setenv once_log "${once_log} kernel=${filesize}"
    if fatload ${once_dev} ${fdt_addr_r} ${once_fdt}; then
      setenv once_log "${once_log} fdt=${filesize}"
      fdt addr ${fdt_addr_r}
      fdt memory ${memory_addr} ${memory_size}
      setenv once_log "${once_log} mem=${memory_size}"
      setenv bootargs ${once_bootargs}
      setenv once_log "${once_log} booti"
      env export -t ${loadaddr} once_log once_kernel once_fdt bootargs
      fatwrite ${once_dev} ${loadaddr} /once-log.txt ${filesize}
      booti ${kernel_addr_r} - ${fdt_addr_r}
      setenv once_log "${once_log} booti-returned"
    else
      setenv once_log "${once_log} fdt-load-failed"
    fi
  else
    setenv once_log "${once_log} kernel-load-failed"
  fi
fi

if test -n "${once_log}"; then
  env export -t ${loadaddr} once_log once_kernel once_fdt bootargs
  fatwrite ${once_dev} ${loadaddr} /once-log.txt ${filesize}
fi
