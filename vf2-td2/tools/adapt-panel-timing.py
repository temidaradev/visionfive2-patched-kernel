from pathlib import Path
p = Path('/home/user/td2-drm-module/panel-ilitek-ili9881c.c')
s = p.read_text()
start = s.index('static const struct drm_display_mode rpi_5inch_default_mode = {')
end = s.index('\n};', start)
block = s[start:end]
assert '.clock\t\t= 83333,' in block
block = block.replace('.clock\t\t= 83333,', '.clock\t\t= 79200,')
block = block.replace('.vsync_start\t= 1280 + 100,', '.vsync_start\t= 1280 + 180,')
block = block.replace('.vsync_end\t= 1280 + 100 + 2,', '.vsync_end\t= 1280 + 180 + 2,')
block = block.replace('.vtotal\t\t= 1280 + 100 + 2 + 100,', '.vtotal\t\t= 1280 + 180 + 2 + 20,')
p.write_text(s[:start] + block + s[end:])
print('5-inch panel: 79.2 MHz actual pixel clock, 180/2/20 vertical porches, total unchanged.')
