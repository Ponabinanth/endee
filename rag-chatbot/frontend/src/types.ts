export interface DocumentSummary {
  document_id: string;
  filename: string;
  title: string;
  source: string;
  chunk_count: number;
  character_count: number;
}

export interface Citation {
  label: string;
  document_id: string;
  title: string;
  source: string;
  chunk_index: number;
  score: number;
  excerpt: string;
}

export interface ChatResponse {
  question: string;
  answer: string;
  mode: string;
  citations: Citation[];
  latency_ms: number;
  retrieval_ms: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

export interface Metrics {
  documents: number;
  chunks: number;
  chats_served: number;
  average_latency_ms: number;
  average_retrieval_ms: number;
}
