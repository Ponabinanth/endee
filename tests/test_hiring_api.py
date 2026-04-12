import unittest

from fastapi.testclient import TestClient

from app.main import app


class HiringApiTests(unittest.TestCase):
    def test_status_and_search_and_rank_work_without_network_services(self):
        with TestClient(app) as client:
            status = client.get("/api/status").json()
            self.assertIn("ready", status)
            self.assertTrue(status["ready"])
            self.assertIn(status["vector_store_backend"], {"memory", "endee"})

            search = client.post("/api/search", json={"query": "Python ML engineer with RAG", "role": "all", "location": "all", "stage": "all", "top_k": 5}).json()
            self.assertIn("results", search)
            self.assertTrue(len(search["results"]) >= 1)

            job = {
                "job_id": "job-ml-engineer",
                "title": "Machine Learning Engineer",
                "description": "Need Python and SQL, RAG experience, 2+ years building ML systems in production.",
                "department": "engineering",
                "location": "Remote",
                "min_years_experience": 2,
                "must_have_skills": ["python", "sql", "ml", "nlp"],
                "nice_to_have_skills": ["fastapi", "docker"],
                "interview_focus": ["python", "rag"],
            }
            rank = client.post("/api/rank", json={"job": job, "query": "", "role": "all", "location": "all", "stage": "all", "top_k": 5}).json()
            self.assertIn("ranked_candidates", rank)
            self.assertTrue(len(rank["ranked_candidates"]) >= 1)
            self.assertIn("overall_score", rank["ranked_candidates"][0])
            self.assertIn("score_breakdown", rank["ranked_candidates"][0])


if __name__ == "__main__":
    unittest.main()

