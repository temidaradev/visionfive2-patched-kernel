obj-m := td2_drm.o
td2_drm-y := vs_dc_hw.o vs_dc.o vs_crtc.o vs_drv.o vs_fb.o vs_gem.o vs_plane.o vs_simple_enc.o
td2_drm-$(CONFIG_VERISILICON_VIRTUAL_DISPLAY) += vs_virtual.o
td2_drm-$(CONFIG_VERISILICON_MMU) += vs_dc_mmu.o
td2_drm-$(CONFIG_VERISILICON_DEC) += vs_dc_dec.o
td2_drm-$(CONFIG_STARFIVE_INNO_HDMI) += inno_hdmi.o starfive_hdmi_audio.o

obj-m += td2_dsi.o

obj-m += panel-ilitek-ili9881c.o
