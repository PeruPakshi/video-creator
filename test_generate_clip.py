import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import generate_clip as clip


class PipelineTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_secret_fails_before_submission(self):
        with patch.object(clip, "api") as api:
            with self.assertRaisesRegex(ValueError, "FAL_KEY"):
                clip.generate("ocean waves", "unused")
            api.assert_not_called()

    @patch.dict(os.environ, {"FAL_KEY": "test-only"})
    def test_queue_to_download(self):
        queued = {"request_id": "test", "status_url": "https://queue.fal.run/status",
                  "response_url": "https://queue.fal.run/response",
                  "cancel_url": "https://queue.fal.run/cancel"}
        media = b"\x00\x00\x00\x18ftypisom" + b"test-fixture"
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            with patch.object(clip, "api", side_effect=[queued, {"status": "IN_QUEUE"},
                    {"status": "COMPLETED"}, {"video": {"url": "https://media.fal.media/test.mp4"}}]) as api, \
                    patch.object(clip.time, "sleep"), \
                    patch.object(clip, "urlopen", return_value=io.BytesIO(media)) as download:
                output = clip.generate("ocean waves", directory)
                self.assertEqual(output.read_bytes(), media)
                self.assertEqual(api.call_count, 4)
                download.assert_called_once_with("https://media.fal.media/test.mp4", timeout=120)
                self.assertIn("result", json.loads((Path(directory) / "request.json").read_text()))

    def test_rejects_credential_forwarding_to_other_hosts(self):
        with self.assertRaisesRegex(ValueError, "Unexpected queue URL"):
            clip.api("https://example.com/status", "secret")

    @patch.dict(os.environ, {"FAL_KEY": "test-only"})
    def test_timeout_attempts_cancel(self):
        queued = {"request_id": "test", "cancel_url": "https://queue.fal.run/cancel"}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory, \
                patch.object(clip, "api", side_effect=[queued, {}]) as api, \
                patch.object(clip.time, "monotonic", side_effect=[0, 2]):
            with self.assertRaises(TimeoutError):
                clip.generate("ocean waves", directory, timeout=1)
            self.assertEqual(api.call_args.kwargs, {"method": "PUT"})


if __name__ == "__main__":
    unittest.main()

