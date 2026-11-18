from pathlib import Path
p = Path('/home/user/td2-drm-module/vs_dc.c')
s = p.read_text()
old = '''	if (crtc_state->encoder_type == DRM_MODE_ENCODER_DSI){
		display.v_sync_start = mode->vsync_start + 1;
		display.v_sync_end = mode->vsync_end - 1;
	}else{
		display.v_sync_start = mode->vsync_start;
		display.v_sync_end = mode->vsync_end;
	}'''
new = '''	/* Preserve short sync pulses: shrinking a two-line pulse makes it zero. */
	display.v_sync_start = mode->vsync_start;
	display.v_sync_end = mode->vsync_end;'''
if old in s:
    s = s.replace(old, new)
elif new not in s:
    raise SystemExit('Unexpected DC sync implementation')
marker = '\tdisplay.sync_mode = crtc_state->sync_mode;'
fix = '''	/* Cadence DPI consumes active-high sync, independent of panel mode flags. */
	if (crtc_state->encoder_type == DRM_MODE_ENCODER_DSI) {
		display.h_sync_polarity = true;
		display.v_sync_polarity = true;
	}

'''
if fix not in s:
    assert s.count(marker) == 1
    s = s.replace(marker, fix + marker)
p.write_text(s)
print('DC sync pulse and DSI polarities fixed')
