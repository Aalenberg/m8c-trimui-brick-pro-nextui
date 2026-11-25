#!/bin/sh

proc_asound=${1:-/proc/asound}
sys_sound=${2:-/sys/class/sound}

card=$(awk '$1 ~ /^[0-9]+$/ && $0 !~ /audiocodec/ {print $1; exit}' \
    "$proc_asound/cards") || exit 1
case "$card" in
    ''|*[!0-9]*) echo "USB output unavailable: no eligible sound card" >&2; exit 1 ;;
esac

id=$(cat "$proc_asound/card$card/id") || exit 1
case "$id" in
    ''|M8|audiocodec|*[!a-zA-Z0-9_]*)
        echo "USB output unavailable: NextUI would control $id instead" >&2
        exit 1
        ;;
esac
device=$(readlink -f "$sys_sound/card$card/device") || exit 1
case "$device" in
    */usb*) ;;
    *) echo "USB output unavailable: first external card is not USB" >&2; exit 1 ;;
esac
if [ ! -f "$proc_asound/card$card/pcm0p/info" ]; then
    echo "USB output unavailable: card $id has no playback device 0" >&2
    exit 1
fi

printf '%s\n' "$id"
