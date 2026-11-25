#!/bin/sh

[ "${DEVICE:-}" = brickpro ] || exit 0
config="${SDCARD_PATH:-/mnt/SDCARD}/.userdata/shared/ledsettings_brickpro.txt"
log="${LOGS_PATH:-/mnt/SDCARD/.userdata/tg5040/logs}/leds-off.txt"
exec >> "$log" 2>&1
if [ ! -r "$config" ]; then
    echo "LED settings unavailable: $config"
    exit 1
fi

if ! awk '
    /^brightness=/ { normal++; if ($0 != "brightness=0") exit 1 }
    /^inbrightness=/ { info++; if ($0 != "inbrightness=0") exit 1 }
    END { if (normal != 5 || info != 5) exit 1 }
' "$config"; then
    echo "LED settings are not all off; leaving boot lighting unchanged"
    exit 0
fi

for name in max_scale max_scale_f1f2 max_scale_lr max_scale_rear; do
    if ! printf '0\n' > "/sys/class/led_anim/$name"; then
        echo "ERROR: could not turn off $name"
        exit 1
    fi
done
echo "Applied all-off LED settings before M8 startup"
