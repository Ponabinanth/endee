import csv
import io
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
            self.assertIn(status["vector_store_state"], {"local", "connected", "fallback", "reconnecting"})
            self.assertIn("vector_store_note", status)

            reconnect = client.post("/api/vector-store/reconnect").json()
            self.assertTrue(reconnect["ready"])
            self.assertIn(reconnect["vector_store_state"], {"local", "connected", "fallback"})

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

            summary = client.post(
                "/api/document-summary",
                json={
                    "candidate": {
                        "candidate_id": "cand-summary",
                        "name": "Priya Shah",
                        "headline": "Senior AI Engineer",
                        "target_role": "AI Engineer",
                        "years_experience": 6.5,
                        "location": "Remote",
                        "skills": ["Python", "FastAPI", "Embeddings"],
                        "resume_text": "Built semantic search and vector ranking systems in Python and FastAPI.",
                        "source": "resume.txt",
                        "stage": "screening",
                    }
                },
            ).json()
            self.assertIn("summary", summary)
            self.assertEqual(summary["candidate"]["name"], "Priya Shah")
            self.assertTrue(summary["highlights"])

            export_response = client.post(
                "/api/export-csv",
                json={
                    "docs": [
                        {
                            "id": "cand-1",
                            "name": "Priya Shah",
                            "headline": "Senior AI Engineer",
                            "target_role": "AI Engineer",
                            "location": "Remote",
                            "years_experience": 6.5,
                            "skills": ["Python", "FastAPI"],
                            "source": "resume.txt",
                            "score": 0.93,
                            "similarity_label": "0.930",
                            "reasons": ["Strong semantic overlap."],
                        }
                    ]
                },
            )
            self.assertEqual(export_response.status_code, 200)
            self.assertIn("text/csv", export_response.headers["content-type"])
            self.assertIn("attachment", export_response.headers["content-disposition"])

            rows = list(csv.DictReader(io.StringIO(export_response.text)))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "Priya Shah")
            self.assertEqual(rows[0]["skills"], "Python; FastAPI")

            comparison = client.post(
                "/api/compare",
                json={
                    "candidate_a": {
                        "candidate_id": "cand-a",
                        "name": "Priya Shah",
                        "headline": "Senior AI Engineer",
                        "target_role": "AI Engineer",
                        "years_experience": 7,
                        "location": "Remote",
                        "skills": ["Python", "FastAPI", "Embeddings", "Vector Databases"],
                        "resume_text": "Built retrieval systems, semantic search, and ranking APIs in Python and FastAPI.",
                        "source": "resume-a.txt",
                        "stage": "screening",
                    },
                    "candidate_b": {
                        "candidate_id": "cand-b",
                        "name": "Jordan Lee",
                        "headline": "Full Stack Engineer",
                        "target_role": "Web Engineer",
                        "years_experience": 4,
                        "location": "Remote",
                        "skills": ["React", "TypeScript", "Node.js"],
                        "resume_text": "Built dashboards and frontends with React and TypeScript.",
                        "source": "resume-b.txt",
                        "stage": "screening",
                    },
                    "job": {
                        "job_id": "job-compare",
                        "title": "AI Engineer",
                        "description": "Need Python, FastAPI, embeddings, vector databases, and LLM experience.",
                        "department": "engineering",
                        "location": "Remote",
                        "min_years_experience": 5,
                        "must_have_skills": ["Python", "FastAPI", "Embeddings", "Vector Databases"],
                        "nice_to_have_skills": ["LLMs", "Evaluation"],
                        "interview_focus": ["retrieval quality", "system design"],
                    },
                },
            ).json()
            self.assertIn("summary", comparison)
            self.assertIn("recommendation", comparison)
            self.assertIn(comparison["winner"], {"cand-a", "cand-b", "tie"})
            self.assertGreater(comparison["score_a"], comparison["score_b"])
            self.assertTrue(comparison["shared_skills"] or comparison["unique_skills_a"] or comparison["unique_skills_b"])


if __name__ == "__main__":
    unittest.main()
