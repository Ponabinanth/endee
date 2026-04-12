import unittest

from app.rag import extractive_answer, tokenize


class RagTests(unittest.TestCase):
    def test_tokenize_strips_stopwords(self):
        tokens = tokenize("What is the rollback process for a production release?")
        self.assertIn("rollback", tokens)
        self.assertNotIn("the", tokens)

    def test_extractive_answer_returns_citations(self):
        hits = [
            {
                "title": "Engineering Release Process",
                "source": "knowledge-base/engineering/release-process.md",
                "department": "engineering",
                "doc_type": "runbook",
                "audience": "internal",
                "score": 0.91,
                "text": "Rollback is part of the release, not an afterthought. If a release causes a critical alert, stop the rollout and page the on-call engineer.",
            }
        ]
        result = extractive_answer("What is the rollback process?", hits)
        self.assertEqual(result["mode"], "extractive")
        self.assertTrue(result["citations"])
        self.assertIn("rollback", result["answer"].lower())


if __name__ == "__main__":
    unittest.main()

