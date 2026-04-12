import unittest

from app.scoring import (
    CandidateProfile,
    JobRole,
    build_rank_breakdown,
    evaluate_interview_answers,
    fraud_assessment,
    generate_interview_questions,
    resume_feedback,
)


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.candidate = CandidateProfile(
            id="cand-1",
            name="Priya Shah",
            headline="Senior AI Engineer",
            years_experience=6.5,
            location="Remote",
            target_role="AI Engineer",
            skills=("Python", "FastAPI", "embeddings", "LLMs"),
            resume_text="Built semantic search and vector ranking systems in Python and FastAPI.",
            source="resume.txt",
            summary="Strong semantic search background.",
            projects=("Semantic Search",),
        )
        self.job = JobRole(
            id="job-1",
            title="Senior AI Engineer",
            department="engineering",
            location="Remote",
            min_years_experience=5,
            must_have_skills=("Python", "FastAPI", "embeddings", "vector databases"),
            nice_to_have_skills=("LLMs", "evaluation"),
            description="Design semantic matching and explainable scoring for hiring.",
            interview_focus=("retrieval quality", "evaluation"),
        )

    def test_build_rank_breakdown_returns_reasons(self):
        breakdown = build_rank_breakdown(self.candidate, self.job, semantic_score=0.86)
        self.assertGreater(breakdown["overall_score"], 0)
        self.assertTrue(breakdown["reasons"])

    def test_generate_interview_questions_are_tailored(self):
        questions = generate_interview_questions(self.candidate, self.job, count=4)
        self.assertEqual(len(questions), 4)
        self.assertIn("question", questions[0])
        self.assertIn("expected_signal", questions[0])

    def test_fraud_assessment_flags_suspicious_activity(self):
        result = fraud_assessment(
            {
                "tab_switches": 2,
                "copy_events": 1,
                "paste_events": 1,
                "blur_events": 1,
                "idle_seconds": 140,
                "multiple_faces_detected": True,
            }
        )
        self.assertGreater(result["fraud_score"], 0)
        self.assertTrue(result["flags"])

    def test_interview_evaluation_scores_and_feedback(self):
        result = evaluate_interview_answers(
            self.candidate,
            self.job,
            [{"prompt": "Tell me about a project.", "answer": "I built a semantic search system in Python."}],
            {"tab_switches": 0, "copy_events": 0, "paste_events": 0, "blur_events": 0, "idle_seconds": 10},
        )
        self.assertIn("overall_score", result)
        self.assertTrue(result["suggestions"])

    def test_resume_feedback_highlights_gap(self):
        result = resume_feedback(self.candidate, self.job)
        self.assertIn("summary", result)
        self.assertTrue(result["suggestions"])


if __name__ == "__main__":
    unittest.main()
