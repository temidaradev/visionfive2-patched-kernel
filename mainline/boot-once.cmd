# One-shot boot for the VisionFive 2 (vendor U-Boot 2021.10 runs /boot.scr before extlinux).
# /boot-once holds "1" to boot the mainline kernel exactly once. The flag is cleared
# *before* booting, so any later reset returns to the normal extlinux default.
# Progress is written to /boot/once-log.txt (no serial console needed to debug).
setenv once_dev mmc ${devnum}:${distro_bootpart}
if test -e ${once_dev} /boot-once; then
  if fatload ${once_dev} ${loadaddr} /boot-once 1; then
    if itest.b *${loadaddr} == 0x31; then
      setenv once_log "flag=1"
      if fatload ${once_dev} ${loadaddr} /boot-once.clear 1 && fatwrite ${once_dev} ${loadaddr} /boot-once 1; then
        setenv once_log "${once_log} cleared"
        if fatload ${once_dev} ${loadaddr} /once.env; then
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
            env export -t ${loadaddr} once_log once_kernel once_fdt bootargs kernel_addr_r kernel_comp_addr_r kernel_comp_size fdt_addr_r fdt_high fdtcontroladdr
            fatwrite ${once_dev} ${loadaddr} /once-log.txt ${filesize}
            booti ${kernel_addr_r} - ${fdt_addr_r}
            setenv once_log "${once_log} booti-returned"
          else
            setenv once_log "${once_log} fdt-load-failed"
          fi
        else
          setenv once_log "${once_log} kernel-load-failed"
        fi
        env export -t ${loadaddr} once_log once_kernel once_fdt bootargs kernel_addr_r kernel_comp_addr_r kernel_comp_size fdt_addr_r fdt_high fdtcontroladdr
        fatwrite ${once_dev} ${loadaddr} /once-log.txt ${filesize}
      fi
    fi
  fi
fi
