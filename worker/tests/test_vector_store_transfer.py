import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from schemas.document import Chunk
from vector_store.simple_store import SimpleVectorStore


class SimpleVectorStoreTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SimpleVectorStore(self.temp_dir.name)
        self.store.upsert(
            [Chunk(id="chunk-1", book_id="book-1", chapter_id="chapter-1", content="old")],
            [[1.0, 0.0]],
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_staging_does_not_replace_target_until_commit(self):
        self.store.import_records(
            "stage-1",
            [
                {
                    "id": "chunk-1",
                    "chapter_id": "chapter-1",
                    "content": "new",
                    "position": 0,
                    "token_count": 1,
                    "start_offset": 0,
                    "end_offset": 3,
                    "vector": [0.0, 1.0],
                }
            ],
        )

        self.assertEqual(self.store.all(["book-1"])[0]["content"], "old")
        self.store.commit_import("book-1", "stage-1", "backup-1")
        imported = self.store.all(["book-1"])
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0]["content"], "new")
        self.assertEqual(imported[0]["vector"], [0.0, 1.0])

    def test_rollback_restores_previous_vector_records(self):
        self.store.import_records(
            "stage-1",
            [
                {
                    "id": "chunk-1",
                    "chapter_id": "chapter-1",
                    "content": "new",
                    "position": 0,
                    "token_count": 1,
                    "start_offset": 0,
                    "end_offset": 3,
                    "vector": [0.0, 1.0],
                }
            ],
        )
        self.store.commit_import("book-1", "stage-1", "backup-1")
        self.store.rollback_import("book-1", "stage-1", "backup-1")

        restored = self.store.all(["book-1"])
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0]["content"], "old")
        self.assertEqual(restored[0]["vector"], [1.0, 0.0])


if __name__ == "__main__":
    unittest.main()
