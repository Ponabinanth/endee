import unittest

from fastapi.testclient import TestClient

from app.main import app, store


class RagApiTests(unittest.TestCase):
    def test_health_chat_and_documents_flow(self):
        store.documents.clear()
        store.chunks.clear()
        store.save()

        client = TestClient(app)

        health = client.get("/health").json()
        self.assertEqual(health["status"], "ok")

        upload = client.post(
            "/ingest",
            json={
                "files": [
                    {
                        "filename": "runbook.txt",
                        "content": "Rollback is required when production alerts fire. Stop rollout and restore the previous image.",
                    }
                ]
            },
        )
        self.assertEqual(upload.status_code, 200)
        payload = upload.json()
        self.assertEqual(payload["chunks_indexed"], 1)

        chat = client.post("/chat", json={"question": "What happens during rollback?", "top_k": 3})
        self.assertEqual(chat.status_code, 200)
        answer = chat.json()
        self.assertIn("rollback", answer["answer"].lower())
        self.assertTrue(answer["citations"])

        document_id = payload["documents"][0]["document_id"]
        delete = client.delete(f"/documents/{document_id}")
        self.assertEqual(delete.status_code, 200)


if __name__ == "__main__":
    unittest.main()
