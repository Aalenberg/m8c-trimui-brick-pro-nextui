#!/usr/bin/env python3
"""Assemble an installation ZIP from the verified device runtime."""

import argparse
import hashlib
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_HASHES = {
    "m8c-bin": "bce77afa40469f9bae01715bfce23711a06e249bd192266f4b98020c64232a30",
    "sink-test": "e361ebc69af157e248c5fd69e24e8d7060d58ed32413a272cb619087ad7aef1f",
    "lib/libSDL3.so.0": "15218218fa16ea0f3dcd1acb6aa7ea4ad97596212a760ca3ba32c491d93f457f",
    "lib/libserialport.so.0": "cd5afca32642b10a2fa593cd5f577d05331f140d3a757a680fd006fa5fd259e2",
    "m8c/gamecontrollerdb.txt": "9ac0ae58a9e7248a01aff469db2215ac85689ef7fe2385f20b8e142d511bcd9a",
    "source/libserialport_0.1.1.orig.tar.xz": "56e857aab85832e276a8d0deedf2ff4be718722f83ac2055b3a7c955119ad4dd",
    "source/libserialport_0.1.1-4.debian.tar.xz": "20b3ea8dc494dc60552cdf55f16155c939534051be70e77278cb1cd0d12faa61",
    "source/libserialport_0.1.1-4.dsc": "56059a0628821bcc4fea7d286e3b60d8cca50ecfc0395f9030a2ef9690e96937",
}
NOTICE_FILES = (
    "LICENSE-Brick-port.txt",
    "LICENSE-SDL.txt",
    "LICENSE-libserialport.txt",
    "LICENSE-m8c.txt",
    "COPYING-GPL-3.txt",
    "COPYING-LGPL-3.txt",
)
PAK = "Tools/tg5040/M8C Install.pak"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    files = {}
    for relative, expected in RUNTIME_HASHES.items():
        path = args.runtime / relative
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise SystemExit(f"Unexpected SHA-256 for {path}: {actual}")
        files[relative] = data

    entries = {}
    for name in ("launch.sh", "INSTALL.txt"):
        path = ROOT / "installer" / name
        entries[f"{PAK}/{name}"] = (
            path.read_bytes(), 0o755 if name.endswith(".sh") else 0o644
        )
    for name in ("launch.sh", "usb-output.sh"):
        entries[f"{PAK}/payload/M8C.pak/{name}"] = ((ROOT / name).read_bytes(), 0o755)
    for name in ("m8-autostart.sync.sh", "00-leds-off.sync.sh"):
        entries[f"{PAK}/{name}"] = ((ROOT / name).read_bytes(), 0o755)
    for name, data in files.items():
        if name.startswith("source/"):
            entries[f"source/{name.removeprefix('source/')}"] = (data, 0o644)
        else:
            mode = 0o755 if name in ("m8c-bin", "sink-test") else 0o644
            entries[f"{PAK}/payload/M8C.pak/{name}"] = (data, mode)
    for name in NOTICE_FILES:
        entries[f"{PAK}/payload/M8C.pak/notices/{name}"] = (
            (args.runtime / "notices" / name).read_bytes(), 0o644
        )
    entries[f"{PAK}/payload/M8C.pak/m8c/config.ini"] = (
        (ROOT / "tools" / "default-config.ini").read_bytes(), 0o644
    )
    entries["INSTALL.txt"] = ((ROOT / "installer" / "INSTALL.txt").read_bytes(), 0o644)

    with args.output.open("xb") as target:
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, (content, mode) in sorted(entries.items()):
                entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = (stat.S_IFREG | mode) << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, content)
    print(f"Created {args.output}")
    print(f"SHA-256: {hashlib.sha256(args.output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
