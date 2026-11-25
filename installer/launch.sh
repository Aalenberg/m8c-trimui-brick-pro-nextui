#!/bin/sh

# NextUI runs Tools from their pak directory and normally hides their output.
cd "$(dirname "$0")" || exit 1
installer_dir=$PWD
exec >> "$installer_dir/log.txt" 2>&1

message() {
    echo "$1"
    if command -v show2.elf >/dev/null 2>&1; then
        show2.elf --mode=progress --image="${SDCARD_PATH:-/mnt/SDCARD}/.system/res/logo.png" \
            --text="$1" --progress=0 &
        show_pid=$!
        sleep 4
        if kill -KILL "$show_pid" 2>/dev/null; then
            wait "$show_pid" 2>/dev/null || :
        else
            wait "$show_pid"
            echo "WARNING: Could not display installer message."
        fi
    else
        echo "WARNING: show2.elf unavailable; see installer log for this message."
    fi
}

exists() { [ -e "$1" ] || [ -L "$1" ]; }
fail() { message "ERROR: $1"; exit 1; }
create_file() { (set -C; cat "$1" > "$2"); }

sd=${SDCARD_PATH:-/mnt/SDCARD}
userdata=${USERDATA_PATH:-$sd/.userdata/tg5040}
tools=$sd/Tools/tg5040
pak=$tools/M8C.pak
hooks=$userdata/.hooks/boot.d
auto=$hooks/m8-autostart.sync.sh
led_hook=$hooks/00-leds-off.sync.sh
config=$userdata/.m8-autostart-path
shared=$sd/.userdata/shared
led=$shared/ledsettings_brickpro.txt
led_tmp=$shared/.m8-installer-led.tmp
state=$userdata/.m8-installer-state

# Never remove an artifact which differs from the installer's saved copy.
matches_or_absent() {
    ! exists "$1" || { [ -f "$1" ] && [ ! -L "$1" ] && cmp -s "$1" "$2"; }
}

restore() {
    [ -f "$state/ready" ] && [ ! -L "$state" ] || {
        message "ERROR: No complete installer state at $state; preserve it for manual recovery."
        return 1
    }
    matches_or_absent "$auto" "$state/autostart" &&
        matches_or_absent "$led_hook" "$state/led-hook" &&
        matches_or_absent "$config" "$state/path" || {
        message "ERROR: An installed hook or path was changed; no restore performed."
        return 1
    }
    # An absent settings file is not proof that restoring it is safe.
    led_needs_restore=no
    if [ -f "$state/led-written" ]; then
        if [ -f "$led" ] && [ ! -L "$led" ] && cmp -s "$led" "$state/led-off"; then
            led_needs_restore=yes
        elif [ -f "$state/led-existed" ] && [ -f "$led" ] && [ ! -L "$led" ] &&
            cmp -s "$led" "$state/led-source"; then
            :
        elif [ ! -f "$state/led-existed" ] && ! exists "$led"; then
            :
        else
            message "ERROR: LED settings changed or disappeared; no restore performed. Backup is in $state."
            return 1
        fi
    fi
    if exists "$led_tmp"; then
        if [ "$led_needs_restore" = yes ] && [ -f "$state/led-existed" ]; then
            message "ERROR: $led_tmp exists; preserve it and resolve the conflict first."
            return 1
        else
            message "Warning: retained $led_tmp for manual inspection."
        fi
    fi
    if [ "$led_needs_restore" = yes ] && [ -f "$state/led-existed" ]; then
        [ -f "$state/led-backup" ] && [ ! -L "$state/led-backup" ] &&
            cmp -s "$state/led-backup" "$state/led-source" || {
            message "ERROR: LED backup is missing or changed; no restore performed."
            return 1
        }
    fi
    if [ "$led_needs_restore" = yes ]; then
        if [ -f "$state/led-existed" ]; then
            (set -C; : > "$led_tmp") && cp -p "$state/led-backup" "$led_tmp" &&
                mv "$led_tmp" "$led" || {
                message "ERROR: Could not restore LED settings; backup remains in $state."
                return 1
            }
        else
            rm "$led" || { message "ERROR: Could not remove installer-created LED settings."; return 1; }
        fi
    fi
    if [ -f "$state/led-written" ]; then rm "$state/led-written" || return 1; fi
    for file in "$auto" "$led_hook" "$config"; do
        if exists "$file"; then
            rm "$file" || { message "ERROR: Could not remove $file"; return 1; }
        fi
    done
    message "M8C hooks restored. Reboot for LED settings. M8C.pak and backup were retained."
}

case ${1:-install} in
    restore)
        restore
        exit $?
        ;;
    install) ;;
    *) fail "Use install or restore." ;;
esac

[ "${DEVICE:-}" = brickpro ] || fail "This installer requires a Brick Pro."
for item in "$pak" "$auto" "$led_hook" "$config" "$state" "$led_tmp"; do
    ! exists "$item" || fail "Already exists: $item. Nothing was overwritten."
done
[ -f "$installer_dir/payload/M8C.pak/launch.sh" ] &&
    [ -f "$installer_dir/m8-autostart.sync.sh" ] &&
    [ -f "$installer_dir/00-leds-off.sync.sh" ] || fail "Installer payload or hooks missing."

if exists "$led"; then
    [ -f "$led" ] && [ ! -L "$led" ] && [ -r "$led" ] || fail "LED settings are not a readable regular file."
    led_source=$led
    led_existed=yes
else
    led_source=$tools/LedControl.pak/ledsettings_brickpro.txt
    [ -f "$led_source" ] && [ ! -L "$led_source" ] && [ -r "$led_source" ] ||
        fail "LED settings missing; install NextUI LedControl's Brick Pro template first."
    led_existed=no
fi

mkdir -p "$userdata" "$hooks" "$shared" "$tools" || fail "Cannot create destination directories."
mkdir "$state" || fail "Cannot create private installer state."
preparation_failed() {
    fail "Preparation failed. No activation performed; preserve $state and inspect log.txt."
}
cp "$installer_dir/m8-autostart.sync.sh" "$state/autostart" &&
    cp "$installer_dir/00-leds-off.sync.sh" "$state/led-hook" &&
    printf '%s\n' "$pak" > "$state/path" &&
    cp -p "$led_source" "$state/led-source" || preparation_failed
if [ "$led_existed" = yes ]; then
    cp -p "$state/led-source" "$state/led-backup" &&
        : > "$state/led-existed" || preparation_failed
fi

# Reject unrecognized or incomplete layouts rather than changing user settings.
cp -p "$state/led-source" "$state/led-off" || preparation_failed
awk '
    /^\[/ {
        if ($0 !~ /^\[(f1|f2|m|lr|rear)\]$/) bad=1
        section=$0; seen[section]++
    }
    /^[[:space:]]*(brightness|inbrightness)[[:space:]]*=/ {
        if ($0 !~ /^(brightness|inbrightness)=[0-9]+$/) bad=1
        split($0, part, "=")
        if (section == "" || part[2] !~ /^[0-9]+$/ || part[2]+0 > 100) bad=1
        count[section,part[1]]++
        print part[1] "=0"
        next
    }
    { print }
    END {
        split("[f1] [f2] [m] [lr] [rear]", zones, " ")
        for (i=1; i<=5; i++)
            if (seen[zones[i]] != 1 || count[zones[i],"brightness"] != 1 ||
                count[zones[i],"inbrightness"] != 1) bad=1
        if (bad) exit 1
    }
' "$state/led-source" > "$state/led-off" || preparation_failed
: > "$state/ready" || preparation_failed

rollback() {
    trap - EXIT HUP INT TERM
    message "ERROR: Installation interrupted or failed; rolling back activation."
    restore || message "ERROR: Automatic rollback incomplete. Keep $state and inspect log.txt."
}
trap rollback EXIT
trap 'exit 1' HUP INT TERM

# Copy the package first; a failed/partial package is retained for inspection,
# never recursively deleted. Hooks are installed last, after LED settings.
mkdir "$pak" || fail "Could not create M8C.pak."
cp -R "$installer_dir/payload/M8C.pak/." "$pak/" || fail "Could not copy M8C.pak."
chmod +x "$pak/launch.sh" || fail "Could not make M8 launcher executable."
create_file "$state/path" "$config" || fail "Could not write autostart path."
if [ "$led_existed" = yes ]; then
    cmp -s "$led" "$state/led-source" || fail "LED settings changed during installation."
else
    ! exists "$led" || fail "LED settings appeared during installation."
fi
create_file "$state/led-off" "$led_tmp" || fail "Could not prepare LED settings."
cp -p "$state/led-off" "$led_tmp" || fail "Could not preserve LED settings permissions."
# Marker precedes replacement so interruption always leaves recovery evidence.
: > "$state/led-written" || fail "Could not record LED replacement."
mv "$led_tmp" "$led" || fail "Could not install LED settings."
create_file "$state/led-hook" "$led_hook" && chmod +x "$led_hook" || fail "Could not install LED hook."
create_file "$state/autostart" "$auto" && chmod +x "$auto" || fail "Could not install autostart hook."
trap - EXIT HUP INT TERM
message "M8C installed. Reboot to apply LED settings and enable autostart."
