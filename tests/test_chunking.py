import unittest

from app.chunking import build_chunk_records, chunk_text


class ChunkingTests(unittest.TestCase):
    def test_chunk_text_creates_overlapping_segments(self):
        text = " ".join(f"word{i}" for i in range(1, 401))
        chunks = chunk_text(text, max_words=120, overlap_words=20)
        self.assertGreaterEqual(len(chunks), 4)
        self.assertTrue(chunks[0].startswith("word1"))
        self.assertIn("word120", chunks[0])
        self.assertIn("word101", chunks[1])

    def test_build_chunk_records_carry_metadata(self):
        records = build_chunk_records(
            document_id="doc-1",
            title="Example",
            source="docs/example.md",
            department="engineering",
            doc_type="runbook",
            audience="internal",
            body="one two three four five six seven eight nine ten eleven twelve",
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].id, "doc-1:001")
        self.assertEqual(records[0].title, "Example")
        self.assertEqual(records[0].department, "engineering")


if __name__ == "__main__":
    unittest.main()

