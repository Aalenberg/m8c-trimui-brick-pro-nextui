#!/bin/sh

cd "$(dirname "$0")" || exit 1
exec > ./log.txt 2>&1

export LD_LIBRARY_PATH="$PWD/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export XDG_CONFIG_HOME="$PWD"
export XDG_DATA_HOME="$PWD"
export SDL_VIDEODRIVER=offscreen
export SDL_VIDEO_DRIVER=offscreen
export SDL_RENDER_DRIVER=software
export SDL_AUDIODRIVER=alsa
export M8C_CONTROL_PROFILE=classic

chmod +x ./m8c-bin ./sink-test || exit 1
if [ ! -d /proc/asound/M8 ]; then
    echo "ERROR: M8 USB audio device not found"
    exit 1
fi

original_sink=$(./sink-test get | awk '/^Audio sink:/ {print $NF}')
usb_card=
if [ "$original_sink" = 2 ]; then
    candidate=$(sh ./usb-output.sh)
    if [ -n "$candidate" ] && amixer -c "$candidate" sget PCM >/dev/null 2>&1; then
        usb_card=$candidate
        echo "Using USB output: $usb_card"
    else
        echo "USB output unavailable or unsupported; using internal output"
    fi
fi
case "$original_sink" in
    0) ;;
    2) [ -n "$usb_card" ] || ./sink-test internal || exit 1 ;;
    *) echo "ERROR: Unsupported NextUI audio sink: $original_sink"; exit 1 ;;
esac

playback_device=Playback
[ -z "$usb_card" ] || playback_device="hw:$usb_card,0"

capture_pid=
playback_pid=
runtime_dir=
cleanup() {
    if [ -n "$capture_pid" ]; then
        kill "$capture_pid" 2>/dev/null
        wait "$capture_pid" 2>/dev/null
    fi
    if [ -n "$playback_pid" ]; then
        kill "$playback_pid" 2>/dev/null
        wait "$playback_pid" 2>/dev/null
    fi
    if [ -n "$runtime_dir" ]; then
        rm -f "$runtime_dir/audio"
        rmdir "$runtime_dir"
    fi
    if [ "$original_sink" = 2 ] && [ -d /proc/asound/M8 ]; then
        current_sink=$(./sink-test get | awk '/^Audio sink:/ {print $NF}')
        if [ "$current_sink" = 0 ]; then
            ./sink-test usb || echo "ERROR: Could not restore the USB audio sink"
        fi
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

runtime_dir=$(mktemp -d /tmp/m8-audio.XXXXXX) || exit 1
mkfifo "$runtime_dir/audio" || exit 1
arecord -D hw:M8,0 -t raw -f S16_LE -r 44100 -c 2 -B 100000 -F 25000 \
    > "$runtime_dir/audio" &
capture_pid=$!
aplay -D "$playback_device" -t raw -f S16_LE -r 44100 -c 2 -B 100000 -F 25000 \
    < "$runtime_dir/audio" &
playback_pid=$!
sleep 2
if ! kill -0 "$capture_pid" 2>/dev/null || ! kill -0 "$playback_pid" 2>/dev/null; then
    echo "ERROR: Could not start M8 USB audio routing"
    exit 1
fi

./m8c-bin &
client_pid=$!
while kill -0 "$client_pid" 2>/dev/null; do
    if ! kill -0 "$capture_pid" 2>/dev/null || ! kill -0 "$playback_pid" 2>/dev/null; then
        echo "ERROR: M8 USB audio routing stopped unexpectedly"
        kill "$client_pid"
        wait "$client_pid"
        exit 1
    fi
    if [ -n "$usb_card" ] && [ "$(sh ./usb-output.sh)" != "$usb_card" ]; then
        echo "ERROR: USB output changed; stopping M8 for safety"
        kill "$client_pid"
        wait "$client_pid"
        exit 1
    fi
    sleep 2
done
wait "$client_pid"
