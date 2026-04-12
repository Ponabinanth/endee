import unittest

from app.filters import build_endee_filter


class FilterTests(unittest.TestCase):
    def test_build_endee_filter_defaults_to_candidate(self):
        clauses = build_endee_filter()
        self.assertEqual(clauses, [{"entity_type": {"$eq": "candidate"}}])

    def test_build_endee_filter_builds_clauses(self):
        clauses = build_endee_filter(entity_type="candidate", role="engineering", location="Remote", stage="screening")
        self.assertEqual(
            clauses,
            [
                {"entity_type": {"$eq": "candidate"}},
                {"target_role": {"$eq": "engineering"}},
                {"location": {"$eq": "Remote"}},
                {"stage": {"$eq": "screening"}},
            ],
        )


if __name__ == "__main__":
    unittest.main()
