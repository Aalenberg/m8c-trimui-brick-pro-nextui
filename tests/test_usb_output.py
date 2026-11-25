import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "usb-output.sh"


class UsbOutputTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.proc = root / "proc"
        self.sys = root / "sys"
        self.device = root / "devices" / "usb1" / "adapter"
        self.proc.mkdir()
        self.sys.mkdir()
        self.device.mkdir(parents=True)

    def add_card(self, index, card_id, usb=True, playback=True):
        card = self.proc / f"card{index}"
        card.mkdir()
        (card / "id").write_text(f"{card_id}\n")
        if playback:
            pcm = card / "pcm0p"
            pcm.mkdir()
            (pcm / "info").touch()
        sys_card = self.sys / f"card{index}"
        sys_card.mkdir()
        (sys_card / "device").symlink_to(self.device if usb else self.proc)

    def select(self, cards):
        (self.proc / "cards").write_text(cards)
        return subprocess.run(
            ["sh", str(SCRIPT), str(self.proc), str(self.sys)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_selects_first_usb_output_after_internal_codec(self):
        self.add_card(1, "A")
        result = self.select(
            " 0 [audiocodec]: audiocodec - audiocodec\n"
            " 1 [A]: USB-Audio - Adapter\n"
            " 2 [M8]: USB-Audio - M8\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "A")

    def test_rejects_m8_before_adapter(self):
        self.add_card(0, "M8")
        result = self.select(" 0 [M8]: USB-Audio - M8\n 2 [A]: USB-Audio - Adapter\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("M8", result.stderr)

    def test_rejects_missing_playback(self):
        self.add_card(0, "A", playback=False)
        result = self.select(" 0 [A]: USB-Audio - Adapter\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no playback", result.stderr)

    def test_rejects_non_usb_card(self):
        self.add_card(0, "Other", usb=False)
        result = self.select(" 0 [Other]: Other audio\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not USB", result.stderr)

    def test_rejects_no_external_card(self):
        result = self.select(" 1 [audiocodec]: audiocodec - audiocodec\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no eligible", result.stderr)


if __name__ == "__main__":
    unittest.main()
