import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ZONES = ("f1", "f2", "m", "lr", "rear")
SETTINGS = "".join(
    f"[{zone}]\neffect=4\nbrightness=75\ninbrightness=42\nfilename={zone}\n\n"
    for zone in ZONES
)
OFF = SETTINGS.replace("brightness=75", "brightness=0").replace(
    "inbrightness=42", "inbrightness=0"
)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "tests", prefix="installer-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.sd = Path(self.temp.name) / "sd"
        self.tools = self.sd / "Tools/tg5040"
        self.installer = self.tools / "M8C Install.pak"
        self.installer.mkdir(parents=True)
        shutil.copy(ROOT / "installer/launch.sh", self.installer / "launch.sh")
        for name in ("m8-autostart.sync.sh", "00-leds-off.sync.sh"):
            shutil.copy(ROOT / name, self.installer / name)
        payload = self.installer / "payload/M8C.pak"
        payload.mkdir(parents=True)
        (payload / "launch.sh").write_text("#!/bin/sh\nexit 0\n")
        (payload / "user-file").write_text("payload")
        self.user = self.sd / ".userdata/tg5040"
        self.shared = self.sd / ".userdata/shared"
        self.shared.mkdir(parents=True)
        self.led = self.shared / "ledsettings_brickpro.txt"
        self.led.write_text(SETTINGS)
        self.hooks = self.user / ".hooks/boot.d"
        self.state = self.user / ".m8-installer-state"
        self.env = dict(os.environ, SDCARD_PATH=str(self.sd), USERDATA_PATH=str(self.user), DEVICE="brickpro")

    def run_installer(self, *args, success=True):
        result = subprocess.run(
            ["sh", str(self.installer / "launch.sh"), *args],
            env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=15,
        )
        log = (self.installer / "log.txt").read_text()
        self.assertEqual(result.returncode == 0, success, log)
        return log

    def test_install_and_restore_existing_settings(self):
        self.led.chmod(0o640)
        self.run_installer()
        self.assertEqual(self.led.read_text(), OFF)
        self.assertEqual(self.led.stat().st_mode & 0o777, 0o640)
        self.assertEqual((self.state / "led-backup").read_text(), SETTINGS)
        self.assertEqual((self.user / ".m8-autostart-path").read_text(), str(self.tools / "M8C.pak") + "\n")
        for name in ("m8-autostart.sync.sh", "00-leds-off.sync.sh"):
            self.assertTrue(os.access(self.hooks / name, os.X_OK))
        self.assertTrue(os.access(self.tools / "M8C.pak/launch.sh", os.X_OK))
        self.run_installer("restore")
        self.assertEqual(self.led.read_text(), SETTINGS)
        self.assertEqual(self.led.stat().st_mode & 0o777, 0o640)
        self.assertFalse((self.hooks / "m8-autostart.sync.sh").exists())
        self.assertFalse((self.hooks / "00-leds-off.sync.sh").exists())
        self.assertFalse((self.user / ".m8-autostart-path").exists())
        self.assertTrue((self.tools / "M8C.pak/user-file").exists())
        self.assertTrue((self.state / "led-backup").exists())
        self.run_installer("restore")

    def test_missing_led_uses_template_then_restore_removes_created_file(self):
        self.led.unlink()
        template = self.tools / "LedControl.pak/ledsettings_brickpro.txt"
        template.parent.mkdir()
        template.write_text(SETTINGS)
        self.run_installer()
        self.assertEqual(self.led.read_text(), OFF)
        self.assertFalse((self.state / "led-backup").exists())
        self.run_installer("restore")
        self.assertFalse(self.led.exists())
        self.assertEqual(template.read_text(), SETTINGS)

    def test_missing_or_invalid_template_does_not_activate(self):
        self.led.unlink()
        self.assertIn("template", self.run_installer(success=False))
        template = self.tools / "LedControl.pak/ledsettings_brickpro.txt"
        template.parent.mkdir()
        template.write_text(SETTINGS.replace("[rear]", "[unknown]"))
        self.run_installer(success=False)
        self.assertFalse((self.tools / "M8C.pak").exists())
        self.assertFalse(self.led.exists())

    def test_refuses_all_existing_destinations_including_dangling_symlinks(self):
        targets = (
            self.tools / "M8C.pak", self.hooks / "m8-autostart.sync.sh",
            self.hooks / "00-leds-off.sync.sh", self.user / ".m8-autostart-path",
            self.state, self.shared / ".m8-installer-led.tmp",
        )
        for target in targets:
            with self.subTest(target=target):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(target.parent / "missing")
                self.run_installer(success=False)
                self.assertTrue(target.is_symlink())
                self.assertEqual(self.led.read_text(), SETTINGS)
                target.unlink()

    def test_changed_files_block_restore_without_any_changes(self):
        self.run_installer()
        hook = self.hooks / "m8-autostart.sync.sh"
        original = hook.read_text()
        hook.write_text("custom")
        self.assertIn("no restore performed", self.run_installer("restore", success=False))
        self.assertEqual(self.led.read_text(), OFF)
        self.assertEqual(hook.read_text(), "custom")
        hook.write_text(original)
        self.led.write_text(SETTINGS.replace("brightness=75", "brightness=55"))
        self.run_installer("restore", success=False)
        self.assertTrue(hook.exists())
        self.assertEqual((self.state / "led-backup").read_text(), SETTINGS)

    def test_failure_after_led_activation_rolls_back(self):
        bindir = Path(self.temp.name) / "bin"
        bindir.mkdir()
        chmod = bindir / "chmod"
        chmod.write_text('#!/bin/sh\ncase "$*" in *m8-autostart.sync.sh*) exit 1;; esac\nexec /bin/chmod "$@"\n')
        chmod.chmod(0o755)
        self.env["PATH"] = str(bindir) + os.pathsep + self.env["PATH"]
        self.assertIn("rolling back activation", self.run_installer(success=False))
        self.assertEqual(self.led.read_text(), SETTINGS)
        self.assertFalse((self.hooks / "m8-autostart.sync.sh").exists())
        self.assertFalse((self.hooks / "00-leds-off.sync.sh").exists())
        self.assertFalse((self.user / ".m8-autostart-path").exists())
        self.assertTrue((self.state / "led-backup").exists())

    def test_recovery_before_led_replace(self):
        self.run_installer()
        self.led.write_text(SETTINGS)
        (self.shared / ".m8-installer-led.tmp").write_text(OFF)
        self.run_installer("restore")
        self.assertEqual(self.led.read_text(), SETTINGS)
        self.assertEqual((self.shared / ".m8-installer-led.tmp").read_text(), OFF)

    def test_changed_backup_blocks_restore(self):
        self.run_installer()
        (self.state / "led-backup").write_text("different")
        self.assertIn("LED backup is missing or changed", self.run_installer("restore", success=False))
        self.assertEqual(self.led.read_text(), OFF)
        self.assertTrue((self.hooks / "m8-autostart.sync.sh").exists())

    def test_malformed_brightness_is_rejected(self):
        self.led.write_text(SETTINGS + " brightness=7\n")
        self.run_installer(success=False)
        self.assertFalse((self.tools / "M8C.pak").exists())
        self.assertFalse((self.user / ".m8-autostart-path").exists())

    def test_wrong_device_does_nothing(self):
        self.env["DEVICE"] = "brick"
        self.run_installer(success=False)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.led.read_text(), SETTINGS)

    def test_notification_uses_nextui_progress_arguments(self):
        bindir = Path(self.temp.name) / "bin"
        bindir.mkdir()
        show = bindir / "show2.elf"
        show.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$@" > "$SDCARD_PATH/show-args"\n'
            "exec /bin/sleep 20\n"
        )
        show.chmod(0o755)
        sleep = bindir / "sleep"
        sleep.write_text("#!/bin/sh\n/bin/sleep 0.1\n")
        sleep.chmod(0o755)
        self.env["PATH"] = str(bindir) + os.pathsep + self.env["PATH"]
        self.env["DEVICE"] = "brick"
        self.run_installer(success=False)
        args = (self.sd / "show-args").read_text().splitlines()
        self.assertIn("--mode=progress", args)
        self.assertIn(f"--image={self.sd}/.system/res/logo.png", args)
        self.assertIn("--text=ERROR: This installer requires a Brick Pro.", args)


if __name__ == "__main__":
    unittest.main()
