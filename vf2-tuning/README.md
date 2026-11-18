# Runtime kernel tuning for the VisionFive 2 desktop

Kernel tunables for running a desktop off an SD card on the JH7110 (4x U74,
8 GB). They change kernel behaviour at runtime only; no kernel rebuild is needed.

| File | Install to | Effect |
|---|---|---|
| `90-starfive-desktop.conf` | `/etc/sysctl.d/` | `vm.swappiness=10`, so SD-card swap is a fallback under memory pressure. Dirty write-back is capped at 32 MB background and 128 MB hard, so large RAM-sized flushes don't stall the SD card. |
| `starfive-desktop-tuning` | `/usr/local/sbin/` | Sets the `ondemand` cpufreq governor and a 50 ms `sampling_rate`. The default polling interval is several seconds, which makes the desktop sluggish to ramp up. |
| `starfive-desktop-tuning.service` | `/etc/systemd/system/` | Runs the script at boot (`systemctl enable starfive-desktop-tuning`). |

The board also uses a swap file with priority 10:
`/swapfile-starfive none swap sw,pri=10 0 0` in `/etc/fstab`.
