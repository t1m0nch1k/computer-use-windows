"""Windows integration checks without mouse clicks, typing or app changes."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
if sys.platform == "win32":
    import capture_store
    import computer
    import overlay
    import screen
    import win_desktop
    from PIL import Image


class Session:
    def __init__(self):
        self.proc = subprocess.Popen([sys.executable, str(SCRIPTS / "computer.py"), "serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8")
        self.lines = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.ready = self.receive()
        if not self.ready.get("ready"):
            self.stop()
            raise RuntimeError(str(self.ready))

    def _read(self):
        for line in self.proc.stdout:
            self.lines.put(line)

    def receive(self):
        return json.loads(self.lines.get(timeout=8))

    def send(self, request):
        self.proc.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        return self.receive()

    def stop(self):
        if self.proc.poll() is None:
            self.proc.stdin.close()
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=3)
        if not self.proc.stdin.closed:
            self.proc.stdin.close()
        self.proc.stdout.close()
        self.proc.stderr.close()


@unittest.skipUnless(sys.platform == "win32", "Windows interactive desktop required")
class DesktopTests(unittest.TestCase):
    def tearDown(self):
        overlay.stop_overlay()

    def test_temporary_capture_and_release(self):
        with tempfile.TemporaryDirectory() as project:
            previous = os.getcwd()
            try:
                os.chdir(project)
                result = screen.capture_screenshot(region=(150, 150, 200, 100), grid=True)
                path = Path(result["path"])
                self.assertEqual(path.parent, capture_store.ROOT)
                self.assertTrue(result["temporary"])
                self.assertEqual(result["origin"], [150, 150])
                self.assertEqual(list(Path(project).iterdir()), [])
                self.assertTrue(capture_store.release(path))
                self.assertFalse(path.exists())
                self.assertFalse(capture_store.release(path))
            finally:
                os.chdir(previous)

    def test_explicit_path_requires_keep(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "screen.png"
            with self.assertRaises(ValueError):
                screen.capture_screenshot(str(path))
            self.assertFalse(path.exists())
            result = screen.capture_screenshot(str(path), region=(0, 0, 64, 64), keep=True)
            self.assertFalse(result["temporary"])
            with self.assertRaises(ValueError):
                capture_store.release(path)
            self.assertTrue(path.exists())

    def test_expiry_survives_capture_process(self):
        script = "import capture_store; p=capture_store.allocate(); p.write_bytes(b'test'); capture_store.expire_later(p, 0.15); print(p)"
        result = subprocess.run([sys.executable, "-c", script], cwd=SCRIPTS,
                                capture_output=True, text=True, check=True, timeout=5)
        path = Path(result.stdout.strip())
        deadline = time.monotonic() + 5
        while path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(path.exists())

    def test_capture_failure_cleans_up(self):
        from unittest.mock import patch
        before = set(capture_store.ROOT.glob("*.png"))
        with patch.object(screen, "capture_screen_raw", side_effect=RuntimeError("capture failed")):
            with self.assertRaises(RuntimeError):
                screen.capture_screenshot()
        self.assertEqual(before, set(capture_store.ROOT.glob("*.png")))

    def test_absolute_grid_and_marker_on_crop(self):
        image = Image.new("RGB", (200, 100), "white")
        self.assertIs(screen.draw_grid_overlay(image, origin=(150, 150)), image)
        self.assertEqual(image.getpixel((50, 60)), (0, 200, 255))
        self.assertEqual(image.getpixel((0, 60)), (255, 255, 255))
        screen.draw_cursor_marker(image, 220, 220, origin=(150, 150))
        self.assertEqual(image.getpixel((70, 70)), (255, 255, 255))
        self.assertEqual(image.getpixel((70, 80)), (255, 0, 0))

    def test_overlay_reuses_process(self):
        first = overlay.start_overlay()
        self.assertEqual(first, overlay.start_overlay())
        self.assertEqual(first, overlay.overlay_status()["pid"])
        self.assertTrue(overlay.stop_overlay())
        self.assertFalse(overlay.overlay_status()["running"])

    def test_session_preserves_process_and_cleans_on_close(self):
        session = Session()
        path = None
        try:
            first = overlay.overlay_status()["pid"]
            result = session.send({"id":"снимок", "action":"screenshot", "crop":[0,0,100,100]})
            self.assertEqual(result["id"], "снимок")
            path = Path(result["result"]["path"])
            self.assertTrue(path.exists())
            self.assertIn("result", session.send({"action":"cursor"}))
            self.assertEqual(first, overlay.overlay_status()["pid"])
            session.send({"action":"close"})
            session.proc.wait(timeout=5)
            self.assertFalse(path.exists())
            self.assertFalse(overlay.overlay_status()["running"])
        finally:
            session.stop()
            if path:
                capture_store.release(path)

    def test_session_eof_cleanup(self):
        session = Session()
        path = None
        try:
            path = Path(session.send({"action":"screenshot", "crop":[0,0,64,64]})["result"]["path"])
            session.stop()
            self.assertFalse(path.exists())
            self.assertFalse(overlay.overlay_status()["running"])
        finally:
            session.stop()
            if path:
                capture_store.release(path)

    def test_cancelled_session_does_not_restart(self):
        session = Session()
        try:
            overlay.stop_overlay()
            self.assertIn("error", session.send({"action":"cursor"}))
            self.assertFalse(overlay.overlay_status()["running"])
            self.assertTrue(session.send({"action":"close"})["closed"])
        finally:
            session.stop()

    def test_batch_stops_at_error_and_keeps_existing_overlay(self):
        first = overlay.start_overlay()
        results = computer.run_batch([{"action":"cursor"}, {"action":"unknown"}, {"action":"cursor"}])
        self.assertEqual([r["status"] for r in results], ["ok", "error"])
        self.assertEqual(first, overlay.overlay_status()["pid"])

    def test_zero_wait_and_invalid_json_recovery(self):
        session = Session()
        try:
            session.proc.stdin.write("not json\n")
            session.proc.stdin.flush()
            self.assertIn("error", session.receive())
            self.assertEqual(session.send({"action":"wait", "seconds":0})["result"]["seconds"], 0)
            self.assertIn("result", session.send({"action":"cursor"}))
        finally:
            session.stop()

    def test_desktop_attachment_reuses_handle(self):
        first = win_desktop.attach_input_desktop()
        self.assertTrue(first)
        for _ in range(100):
            self.assertEqual(first, win_desktop.attach_input_desktop())


if __name__ == "__main__":
    unittest.main()
