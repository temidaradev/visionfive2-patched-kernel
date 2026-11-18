#!/bin/bash
set -euo pipefail
src=/home/user/vf2-sdk/linux
out=/home/user/td2-drm-module
cp "$src/drivers/gpu/drm/verisilicon/starfive_drm_dsi.c" "$out/td2_dsi.c"
python3 - <<'PY'
from pathlib import Path
p = Path('/home/user/td2-drm-module/td2_dsi.c')
s = p.read_text()
s = s.replace('reg_wakeup = (phy_cfg->hs_prepare + phy_cfg->hs_zero) / tx_byte_period;',
              'reg_wakeup = dsi_cfg.htotal / nlanes / 10;')
# Arm the DSI input before CRTC enable starts DPI, as in upstream Cadence.
# Starting it after the source is already streaming loses synchronization.
s = s.replace('.enable = cdns_dsi_bridge_enable,',
              '.pre_enable = cdns_dsi_bridge_enable,')
# Backport the current Cadence timing accounting: sync-event packets have
# a different overhead, and an odd line length is not an invalid mode.
s = s.replace('dsi_cfg->hbp = dpi_to_dsi_timing(tmp, bpp, DSI_HBP_FRAME_OVERHEAD);',
              'dsi_cfg->hbp = dpi_to_dsi_timing(tmp, bpp, sync_pulse ? 12 : 16);')
start = s.index('static int cdns_dsi_adjust_phy_config(')
end = s.index('static int cdns_dsi_bridge_attach(', start)
s = s[:start] + '''static int cdns_dsi_check_conf(struct cdns_dsi *dsi,
                               const struct drm_display_mode *mode,
                               struct cdns_dsi_cfg *cfg, bool check)
{
    struct cdns_dsi_output *out = &dsi->output;
    struct phy_configure_opts_mipi_dphy *phy = &out->phy_opts.mipi_dphy;
    bool pulse = out->dev->mode_flags & MIPI_DSI_MODE_VIDEO_SYNC_PULSE;
    unsigned long pclk = (check ? mode->clock : mode->crtc_clock) * 1000UL;
    u64 line_bytes;
    int ret = cdns_dsi_mode2cfg(dsi, mode, cfg, check);

    if (ret)
        return ret;
    cfg->htotal = cfg->hact + cfg->hfp + DSI_HFP_FRAME_OVERHEAD;
    cfg->htotal += cfg->hbp + (pulse ? 12 : 16);
    if (pulse)
        cfg->htotal += cfg->hsa + DSI_HSA_FRAME_OVERHEAD;
    ret = phy_mipi_dphy_get_default_config(pclk,
              mipi_dsi_pixel_format_to_bpp(out->dev->format),
              out->dev->lanes, phy);
    if (ret)
        return ret;
    phy->hs_clk_rate = roundup(phy->hs_clk_rate, 10000000UL);
    /* The vendor's 12 MHz reference table ends at 1 Gbit/s. */
    if (phy->hs_clk_rate > 1000000000UL || phy->hs_clk_rate < 160000000UL)
        return -ERANGE;
    /* Pad HFP for the M31 PHY's discrete 10 MHz rate steps. */
    line_bytes = (u64)phy->hs_clk_rate * out->dev->lanes *
                 (check ? mode->htotal : mode->crtc_htotal);
    do_div(line_bytes, pclk * 8);
    if (line_bytes < cfg->htotal)
        return -ERANGE;
    cfg->hfp += line_bytes - cfg->htotal;
    cfg->htotal = line_bytes;
    return phy_validate(dsi->dphy, PHY_MODE_MIPI_DPHY, 0, &out->phy_opts);
}

''' + s[end:]
# Match Cadence sync-event vertical packet accounting; the back porch field
# is six bits, and VSYNC contributes an additional line to the sync packet.
s = s.replace('VBP_LEN(mode->crtc_vtotal - mode->crtc_vsync_end) |\n\t       VFP_LEN(mode->crtc_vsync_start - mode->crtc_vdisplay - 1) |\n\t       VSA_LEN(mode->crtc_vsync_end - mode->crtc_vsync_start)',
              'VBP_LEN(mode->crtc_vtotal - mode->crtc_vsync_end - 1) |\n\t       VFP_LEN(mode->crtc_vsync_start - mode->crtc_vdisplay) |\n\t       VSA_LEN(mode->crtc_vsync_end - mode->crtc_vsync_start + 1)')
old_enable = '\tcdns_dsi_check_conf(dsi, mode, &dsi_cfg, false);'
assert s.count(old_enable) == 1
s = s.replace(old_enable, '''\tif (cdns_dsi_check_conf(dsi, mode, &dsi_cfg, false)) {
\t\tdev_err(dsi->base.dev, "Unsupported DSI timing\\n");
\t\tpm_runtime_put(dsi->base.dev);
\t\treturn;
\t}''')
marker = 'static const struct drm_bridge_funcs cdns_dsi_bridge_funcs = {'
assert s.count(marker) == 1
callback = '''/* The panel bridge sends DCS commands in pre_enable, before our enable.
 * Compute PHY timing during mode_set so that those commands cannot power
 * the PHY with the zero hs_clk_rate initially provided by panel attach.
 */
static void td2_dsi_mode_set(struct drm_bridge *bridge,
                             const struct drm_display_mode *mode,
                             const struct drm_display_mode *adjusted_mode)
{
    struct cdns_dsi *dsi = input_to_dsi(bridge_to_cdns_dsi_input(bridge));
    struct cdns_dsi_cfg cfg;
    int ret = cdns_dsi_check_conf(dsi, adjusted_mode, &cfg, false);

    if (ret)
        dsi->output.phy_opts.mipi_dphy.hs_clk_rate = 0;

    dev_info(dsi->base.dev, "TD2 mode_set: clock=%d hs_rate=%lu check=%d\\n",
             adjusted_mode->crtc_clock,
             dsi->output.phy_opts.mipi_dphy.hs_clk_rate, ret);
}

'''
s = s.replace(marker, callback + marker + '\n\t.mode_set = td2_dsi_mode_set,')
s = s.replace('cdns_dsi_platform_driver', 'td2_cdns_dsi_platform_driver')
# A malformed/absent mode must fail rather than enter the vendor PHY's
# unbounded PLL lock wait with a zero bitrate.
old = '\tcdns_dsi_init_link(dsi);\n\n\tret = mipi_dsi_create_packet'
new = '''\tif (!dsi->output.phy_opts.mipi_dphy.hs_clk_rate) {
\t\tret = -EINVAL;
\t\tdev_err(host->dev, "DSI transfer before link timing setup\\n");
\t\tgoto out;
\t}
\tcdns_dsi_init_link(dsi);

\tret = mipi_dsi_create_packet'''
assert old in s
s = s.replace(old, new)
p.write_text(s)
mk = Path('/home/user/td2-drm-module/Makefile')
m = mk.read_text()
if 'obj-m += td2_dsi.o' not in m:
    mk.write_text(m + '\nobj-m += td2_dsi.o\n')
PY
make -C "$src" M="$out" -j3 modules
/sbin/modinfo "$out/td2_dsi.ko"
