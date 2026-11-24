#!/bin/sh

log="${LOGS_PATH:-/mnt/SDCARD/.userdata/tg5040/logs}/m8-autostart.txt"
exec >> "$log" 2>&1

if [ "${DEVICE:-}" != brickpro ]; then
    echo "M8 autostart skipped: not a Brick Pro"
    exit 0
fi

config="${USERDATA_PATH:-/mnt/SDCARD/.userdata/tg5040}/.m8-autostart-path"
if [ ! -r "$config" ] || ! IFS= read -r pak < "$config"; then
    echo "M8 autostart skipped: package path is not configured"
    exit 0
fi
case "$pak" in
    "${SDCARD_PATH:-/mnt/SDCARD}/Tools/tg5040/"*.pak) ;;
    *) echo "M8 autostart skipped: invalid package path"; exit 0 ;;
esac
if [ ! -x "$pak/launch.sh" ]; then
    echo "M8 autostart skipped: launcher missing or not executable"
    exit 0
fi

attempt=0
while [ "$attempt" -lt 20 ]; do
    if [ -d /proc/asound/M8 ] && ls /dev/ttyACM* >/dev/null 2>&1; then
        break
    fi
    sleep 1
    attempt=$((attempt + 1))
done
if [ "$attempt" -ge 20 ]; then
    echo "M8 autostart skipped: USB audio or serial device not ready"
    exit 0
fi

# Give NextUI's audio monitor time to select the USB sink.
sleep 2
for pid in $(pidof show2.elf); do
    case "$(readlink "/proc/$pid/exe")" in
        */show2.elf) kill "$pid" || echo "ERROR: Could not stop boot splash ($pid)" ;;
    esac
done

echo "Starting M8"
sh "$SYSTEM_PATH/bin/governor.sh" performance
"$pak/launch.sh"
status=$?
sh "$SYSTEM_PATH/bin/governor.sh" auto
if [ "$status" -ne 0 ]; then
    echo "ERROR: M8 launcher exited with status $status; returning to NextUI"
fi
exit 0
