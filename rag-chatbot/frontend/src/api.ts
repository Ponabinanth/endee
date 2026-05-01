import type { ChatMessage, ChatResponse, DocumentSummary, Metrics } from "./types";

export async function fetchDocuments(): Promise<DocumentSummary[]> {
  const response = await fetch("/api/documents");
  if (!response.ok) {
    throw new Error("Could not load documents");
  }
  return response.json();
}

export async function fetchMetrics(): Promise<Metrics> {
  const response = await fetch("/api/metrics");
  if (!response.ok) {
    throw new Error("Could not load metrics");
  }
  return response.json();
}

export async function uploadDocuments(files: FileList): Promise<{ documents: DocumentSummary[]; chunks_indexed: number }> {
  const data = new FormData();
  Array.from(files).forEach((file) => data.append("files", file));
  const response = await fetch("/api/upload", {
    method: "POST",
    body: data
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Upload failed");
  }
  return response.json();
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await fetch(`/api/documents/${documentId}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error("Could not delete document");
  }
}

export async function askQuestion(question: string, topK: number, history: ChatMessage[]): Promise<ChatResponse> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK, history })
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Chat request failed");
  }
  return response.json();
}
