import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tubeflow.history import HistoryStore
from tubeflow.jobs import Job, JobManager
from tubeflow.security import TokenStore


class PublicJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.cfg = SimpleNamespace(
            download_dir=root / "downloads",
            max_concurrent=1,
        )
        self.history = HistoryStore(root / "data" / "history.json")
        self.tokens = TokenStore(3600)
        self.manager = JobManager(self.cfg, self.history, self.tokens)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _job(self) -> Job:
        return Job(
            id="d" * 32,
            url="https://www.youtube.com/watch?v=abc123def45",
            mode="mp3",
            quality="320",
            quality_label="320 kbps",
            title="Ornek video",
            thumbnail="",
            uploader="Kanal",
            duration=60,
            duration_text="1:00",
        )

    def test_public_payload_exposes_url_for_retry(self) -> None:
        data = self.manager.public(self._job(), lan_ip=None, lan_port=None)

        self.assertEqual(data["url"], "https://www.youtube.com/watch?v=abc123def45")
        self.assertEqual(data["mode"], "mp3")
        self.assertEqual(data["quality"], "320")


if __name__ == "__main__":
    unittest.main()
