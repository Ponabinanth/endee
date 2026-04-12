import unittest

from app.filters import build_endee_filter


class FilterTests(unittest.TestCase):
    def test_build_endee_filter_omits_all(self):
        self.assertIsNone(build_endee_filter())
        self.assertIsNone(build_endee_filter(department="all", doc_type="all", audience="all"))

    def test_build_endee_filter_builds_clauses(self):
        clauses = build_endee_filter(department="engineering", doc_type="runbook", audience="internal")
        self.assertEqual(
            clauses,
            [
                {"department": {"$eq": "engineering"}},
                {"doc_type": {"$eq": "runbook"}},
                {"audience": {"$eq": "internal"}},
            ],
        )


if __name__ == "__main__":
    unittest.main()

