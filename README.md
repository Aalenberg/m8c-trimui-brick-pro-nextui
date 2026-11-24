# m8c for TrimUI Brick Pro / NextUI

An ARM64 port of [m8c](https://github.com/laamaa/m8c) for using a
Teensy 4.1 running M8 Headless with a TrimUI Brick Pro running
[NextUI](https://github.com/LoveRetro/NextUI). It builds on
[m8c for TrimUI Brick / Knulli](https://github.com/myldy20/m8c-trimui-brick-knulli).

This repository contains the client and NextUI launcher, **not** the M8
Headless firmware.

## Tested setup

- TrimUI Brick Pro, NextUI v6.15.0, `tg5040`
- Teensy 4.1, M8 Headless firmware 6.6.3
- m8c 2.2.3 and SDL 3.2.20

The display, controls, USB audio capture, headphone output and volume buttons
have been tested on this setup. Noise and clicks remain audible on the Brick
Pro's built-in headphone output, including during silent playback with the
Teensy disconnected. Their cause has not been determined.

## Controls

| Brick Pro control | M8 action |
|---|---|
| D-pad | Navigate |
| A | Option |
| B | Edit |
| Select | Shift |
| Start | Play / stop |
| Select + Y | Exit client |

These are the NextUI button names for the classic layout. The port uses raw
joystick buttons, including Brick Pro-specific Play and exit mappings.

## Audio

The installed m8c configuration disables its own capture; the launcher uses ALSA
`arecord` and `aplay` to route 44.1 kHz stereo USB audio from the M8 to the
Brick's `Playback` PCM. It temporarily selects NextUI's internal audio sink
and restores the previous USB sink on normal exit when the M8 is still
connected. Set the volume low before connecting headphones.

If the M8 is absent or the client fails to start, inspect `log.txt` in the
tool's directory. Forced termination or power loss can prevent normal cleanup;
reconnect the Teensy or reboot if routing behaves unexpectedly. This launcher
is intended for the M8 and the internal output; it does not select or manage
an additional USB DAC.

## Source and building

`m8c-source/` contains the modified m8c source used for the installed client.
`launch.sh` and `sink-test.c` are the NextUI launcher and audio-sink helper.
The source snapshot retains upstream documentation; its generic audio guide
does not describe this launcher's ALSA bridge.

The original Brick port uses the following m8c build command in an ARM64 Linux
environment with SDL3 and libserialport development files available:

```sh
cd m8c-source
make CFLAGS="-DBRICK_RAW_CONTROLS"
```

The helper uses `dlopen` to access NextUI's `libmsettings.so` at runtime:

```sh
cc -O2 -o sink-test sink-test.c -ldl
```

Build against libraries compatible with the target NextUI system. The tested
installation uses SDL 3.2.20 and libserialport 0.1.1; the original Brick port's
[build scripts](https://github.com/myldy20/m8c-trimui-brick-knulli/tree/main/scripts)
show its SDL build configuration. These commands have not yet been verified
as a complete, reproducible NextUI build from this repository.

## Installation status

The working client currently exists as a NextUI Tools package on the tested
device. This repository preserves its modified source and launcher, but does
not yet provide a downloadable package or a complete automated installation
procedure. The runtime package needs the ARM64 client as `m8c-bin`, the
`sink-test` helper, compatible SDL3 and libserialport libraries under `lib/`,
and an m8c configuration with `audio_enabled=false`.

## Credits and licenses

- [m8c](https://github.com/laamaa/m8c), by Jonne Kokkonen and contributors:
  see [m8c-source/LICENSE](m8c-source/LICENSE), including font and other
  third-party notices.
- [m8c for TrimUI Brick / Knulli](https://github.com/myldy20/m8c-trimui-brick-knulli),
  by myldy20: see [LICENSE-Brick-port](LICENSE-Brick-port).
- [SDL](https://github.com/libsdl-org/SDL) and
  [libserialport](https://sigrok.org/wiki/Libserialport) are runtime
  dependencies; binaries are not included here.
- [NextUI](https://github.com/LoveRetro/NextUI) provides the system settings
  library used by the sink helper.
