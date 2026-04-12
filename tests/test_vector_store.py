import unittest

from app.vector_store import InMemoryVectorStore


class VectorStoreTests(unittest.TestCase):
    def test_in_memory_vector_store_queries_by_similarity(self):
        store = InMemoryVectorStore()
        store.create_index(name="test", dimension=2)
        index = store.get_index(name="test")
        index.upsert(
            [
                {"id": "a", "vector": [1.0, 0.0], "meta": {"name": "A"}, "filter": {"entity_type": "candidate", "target_role": "AI Engineer"}},
                {"id": "b", "vector": [0.0, 1.0], "meta": {"name": "B"}, "filter": {"entity_type": "candidate", "target_role": "Backend Engineer"}},
            ]
        )

        results = index.query(vector=[1.0, 0.0], top_k=1, filter=[{"entity_type": {"$eq": "candidate"}}])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "a")


if __name__ == "__main__":
    unittest.main()
