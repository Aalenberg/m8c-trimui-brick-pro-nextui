import hashlib
import importlib.util
import sys
import tempfile
import unittest
import zipfile
from configparser import ConfigParser
from pathlib import Path
from unittest.mock import patch


path = Path(__file__).resolve().parents[1] / "tools" / "build-package.py"
spec = importlib.util.spec_from_file_location("build_package", path)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuildPackageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.runtime = root / "runtime"
        self.output = root / "test.zip"
        for folder in (self.repo / "installer", self.runtime / "notices"):
            folder.mkdir(parents=True)
        (self.repo / "tools").mkdir()
        (self.repo / "tools" / "default-config.ini").write_bytes(
            (path.parent / "default-config.ini").read_bytes()
        )
        for name in ("launch.sh", "usb-output.sh", "m8-autostart.sync.sh", "00-leds-off.sync.sh"):
            (self.repo / name).write_text("#!/bin/sh\n")
        (self.repo / "installer" / "launch.sh").write_text("#!/bin/sh\n")
        (self.repo / "installer" / "INSTALL.txt").write_text("Installation\n")
        for name in builder.NOTICE_FILES:
            (self.runtime / "notices" / name).write_text("License\n")
        (self.runtime / "m8c-bin").write_bytes(b"test runtime")
        self.hashes = {"m8c-bin": hashlib.sha256(b"test runtime").hexdigest()}

    def build(self):
        with patch.object(builder, "ROOT", self.repo), patch.object(
            builder, "RUNTIME_HASHES", self.hashes
        ), patch.object(
            sys, "argv", ["build-package", "--runtime", str(self.runtime), "--output", str(self.output)]
        ):
            builder.main()

    def test_builds_valid_archive_and_disables_builtin_audio(self):
        (self.repo / "installer" / "log.txt").write_text("private")
        self.build()
        with zipfile.ZipFile(self.output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertNotIn(f"{builder.PAK}/log.txt", archive.namelist())
            config = ConfigParser()
            config.read_string(archive.read(f"{builder.PAK}/payload/M8C.pak/m8c/config.ini").decode())
            self.assertFalse(config.getboolean("audio", "audio_enabled"))
            self.assertFalse(config.getboolean("gamepad", "gamepad_analog_invert"))
            self.assertEqual(config.getint("graphics", "wait_packets"), 1024)
            self.assertEqual(
                archive.read(f"{builder.PAK}/payload/M8C.pak/m8c-bin"), b"test runtime"
            )
            self.assertEqual(
                (archive.getinfo(f"{builder.PAK}/launch.sh").external_attr >> 16) & 0o777,
                0o755,
            )

    def test_rejects_modified_runtime(self):
        (self.runtime / "m8c-bin").write_bytes(b"unexpected")
        with self.assertRaises(SystemExit):
            self.build()
        self.assertFalse(self.output.exists())

    def test_does_not_overwrite_an_existing_archive(self):
        self.output.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(self.output.read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
