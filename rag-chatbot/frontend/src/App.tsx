import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Boxes,
  CheckCircle2,
  Cloud,
  Code2,
  Database,
  FileText,
  Gauge,
  GitBranch,
  GraduationCap,
  Layers3,
  Loader2,
  Lock,
  MessageSquare,
  Monitor,
  Rocket,
  Search,
  Send,
  Server,
  ShieldCheck,
  Sparkles,
  Trash2,
  UploadCloud
} from "lucide-react";
import { askQuestion, deleteDocument, fetchDocuments, fetchMetrics, uploadDocuments } from "./api";
import type { ChatMessage, DocumentSummary, Metrics } from "./types";

const phases = [
  {
    week: "Week 1-2",
    title: "Foundation & Setup",
    goal: "Understand RAG architecture, set up the repo, install dependencies, and prepare API keys.",
    items: ["RAG fundamentals", "FastAPI + React workspace", "OpenAI and vector DB config"]
  },
  {
    week: "Week 2-3",
    title: "Backend Core",
    goal: "Build ingestion, chunking, embeddings, vector search, RAG chain, and FastAPI routes.",
    items: ["PDF/TXT/DOCX ingestion", "Semantic retrieval", "Cited chat endpoint"]
  },
  {
    week: "Week 3-4",
    title: "Frontend Implementation",
    goal: "Create the document manager, chat UI, loading states, file upload flow, and persisted history.",
    items: ["Chat interface", "Document panel", "API integration"]
  },
  {
    week: "Week 4-5",
    title: "Advanced RAG",
    goal: "Add multi-query retrieval, hybrid search, compression, memory, logging, and evaluation hooks.",
    items: ["Query optimization", "Conversation memory", "RAG quality metrics"]
  },
  {
    week: "Week 5-6",
    title: "Testing & Optimization",
    goal: "Cover backend units, frontend flows, edge cases, latency, security, and input validation.",
    items: ["Unit tests", "Latency targets", "Rate limits and validation"]
  },
  {
    week: "Week 6-7",
    title: "Deployment & CI/CD",
    goal: "Containerize the stack, deploy frontend and backend, and automate test gates on merge.",
    items: ["Docker", "Cloud Run or AWS", "GitHub Actions"]
  },
  {
    week: "Week 7-8",
    title: "Production Hardening",
    goal: "Add observability, docs, dashboards, user feedback, load testing, and scale plans.",
    items: ["Sentry/DataDog", "Deployment guide", "k6 load tests"]
  }
];

const deliverables = [
  { icon: FileText, title: "Document Ingestion", text: "Load PDFs, TXT, Markdown, and DOCX files, normalize text, chunk with overlap, and retain metadata." },
  { icon: Database, title: "Vector Store", text: "Generate embeddings, upsert chunks, run semantic search, and prepare migration paths for Pinecone, Weaviate, or Chroma." },
  { icon: Sparkles, title: "RAG Chain", text: "Combine retrieval, context-aware prompting, citations, response timing, and optional OpenAI generation." },
  { icon: Server, title: "FastAPI Backend", text: "Expose upload, chat, document listing, deletion, health, metrics, and streaming-ready endpoints." },
  { icon: Monitor, title: "React Frontend", text: "Provide a polished chat workspace, upload panel, live metrics, citation previews, and responsive project pages." },
  { icon: ShieldCheck, title: "Production Layer", text: "Add tests, logging, validation, rate limiting, deployment scripts, CI checks, and monitoring hooks." }
];

const resources = [
  ["DeepLearning.AI RAG", "https://www.deeplearning.ai/short-courses/"],
  ["LangChain", "https://github.com/langchain-ai/langchain"],
  ["OpenAI API", "https://platform.openai.com/"],
  ["Pinecone", "https://www.pinecone.io/"],
  ["FastAPI", "https://fastapi.tiangolo.com/"],
  ["React", "https://react.dev/"],
  ["RAG Paper", "https://arxiv.org/abs/2005.11401"],
  ["Fast.ai", "https://www.fast.ai/"]
];

const variations = [
  ["Customer Support Bot", "FAQ training, ticket creation, sentiment analysis, and escalation workflows."],
  ["Internal Knowledge Base", "Confluence or Notion connectors, multi-user access, and document versioning."],
  ["Research Paper Analyzer", "Scientific PDF ingestion, key finding extraction, and literature review generation."],
  ["Multi-Language Support", "Language detection, translation pipeline, and localized answers."]
];

const successCriteria = [
  "Working RAG chatbot answering from custom documents",
  "Full-stack FastAPI and React application",
  "Tests, logging, validation, and error handling",
  "Cloud deployment with a public URL",
  "Clear README, API docs, and architecture notes",
  "Latency and retrieval-quality benchmarks",
  "Scalable design for thousands of documents"
];

const weeklyQuestions = [
  "Did I complete this week's phase?",
  "Is my code on GitHub with good commit messages?",
  "Did I test the features I built?",
  "Can I explain the architecture clearly?",
  "What challenge did I hit, and how did I solve it?",
  "What would I improve next time?"
];

function App() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "Upload a document, then ask a grounded question. Answers include citations from your indexed files."
    }
  ]);
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(5);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [metrics, setMetrics] = useState<Metrics | null>(null);

  const totalChunks = useMemo(
    () => documents.reduce((total, document) => total + document.chunk_count, 0),
    [documents]
  );

  async function refreshDocuments() {
    setDocuments(await fetchDocuments());
  }

  async function refreshMetrics() {
    setMetrics(await fetchMetrics());
  }

  useEffect(() => {
    refreshDocuments().catch((error) => setStatus(error.message));
    refreshMetrics().catch(() => undefined);
  }, []);

  async function handleUpload(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    try {
      const result = await uploadDocuments(files);
      setStatus(`Indexed ${result.chunks_indexed} chunks from ${result.documents.length} document(s).`);
      await refreshDocuments();
      await refreshMetrics();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(documentId: string) {
    setBusy(true);
    try {
      await deleteDocument(documentId);
      await refreshDocuments();
      await refreshMetrics();
      setStatus("Document deleted.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || busy) return;

    setQuestion("");
    setBusy(true);
    setMessages((current) => [...current, { role: "user", content: trimmed }]);

    try {
      const history = messages.slice(-8).map(({ role, content }) => ({ role, content }));
      const response = await askQuestion(trimmed, topK, history);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.answer,
          citations: response.citations
        }
      ]);
      setStatus(`Mode: ${response.mode} | Retrieval: ${response.retrieval_ms}ms | Total: ${response.latency_ms}ms`);
      await refreshMetrics();
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: "assistant", content: error instanceof Error ? error.message : "Question failed" }
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="site-shell">
      <nav className="topbar" aria-label="Primary navigation">
        <a className="logo" href="#overview">
          <Boxes size={24} />
          <span>RAG Production System</span>
        </a>
        <div className="nav-links">
          <a href="#roadmap">Roadmap</a>
          <a href="#architecture">Architecture</a>
          <a href="#workbench">Workbench</a>
          <a href="#resources">Resources</a>
        </div>
      </nav>

      <section id="overview" className="hero-section">
        <div className="hero-copy">
          <p className="eyebrow">6-8 week implementation guide</p>
          <h1>Production-Ready RAG Chatbot System</h1>
          <p className="hero-lede">
            Build a full-stack Retrieval Augmented Generation chatbot that uploads documents,
            retrieves the right context, generates grounded answers, and demonstrates production
            engineering from API design to deployment.
          </p>
          <div className="hero-actions">
            <a className="primary-action" href="#workbench">
              Open live workbench <ArrowRight size={18} />
            </a>
            <a className="secondary-action" href="#roadmap">View 8-week roadmap</a>
          </div>
          <div className="hero-stats" aria-label="Project highlights">
            <strong>FastAPI</strong>
            <strong>React + TypeScript</strong>
            <strong>OpenAI / LLaMA</strong>
            <strong>Pinecone / Chroma</strong>
          </div>
        </div>

        <div className="hero-visual" aria-label="RAG system preview">
          <div className="visual-toolbar">
            <span />
            <span />
            <span />
            <b>rag-chatbot</b>
          </div>
          <div className="visual-grid">
            <div className="visual-node active">
              <UploadCloud size={20} />
              <span>Upload PDFs</span>
            </div>
            <div className="visual-node">
              <Layers3 size={20} />
              <span>Chunk text</span>
            </div>
            <div className="visual-node">
              <Database size={20} />
              <span>Embed vectors</span>
            </div>
            <div className="visual-node wide">
              <Search size={20} />
              <span>Retrieve context with citations</span>
            </div>
            <div className="visual-node wide accent">
              <MessageSquare size={20} />
              <span>Generate grounded answer</span>
            </div>
          </div>
        </div>
      </section>

      <section className="section applications">
        <div className="section-heading">
          <p className="eyebrow">Project overview</p>
          <h2>What This System Solves</h2>
          <p>
            RAG is the core production pattern for AI products that need trusted answers from
            private, changing, or domain-specific knowledge.
          </p>
        </div>
        <div className="application-grid">
          {["Customer support", "Internal knowledge bases", "Legal and medical QA", "Research paper analysis"].map((item) => (
            <article key={item}>
              <CheckCircle2 size={22} />
              <span>{item}</span>
            </article>
          ))}
        </div>
      </section>

      <section id="roadmap" className="section">
        <div className="section-heading">
          <p className="eyebrow">Roadmap</p>
          <h2>Complete 6-8 Week Build Plan</h2>
          <p>Each phase has a clear learning goal, concrete deliverables, and portfolio-visible output.</p>
        </div>
        <div className="timeline">
          {phases.map((phase) => (
            <article className="phase-card" key={phase.title}>
              <span className="phase-week">{phase.week}</span>
              <h3>{phase.title}</h3>
              <p>{phase.goal}</p>
              <ul>
                {phase.items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <section id="architecture" className="section architecture-section">
        <div className="section-heading">
          <p className="eyebrow">Technical architecture</p>
          <h2>Frontend, API, Retrieval, and Model Layers</h2>
          <p>The application separates user experience, orchestration, retrieval storage, and model generation.</p>
        </div>
        <div className="architecture-map">
          <div className="arch-box frontend">
            <Monitor size={26} />
            <h3>React Frontend</h3>
            <p>Chat UI, document manager, settings, metrics, and responsive portfolio pages.</p>
          </div>
          <div className="arch-line" />
          <div className="arch-box backend">
            <Server size={26} />
            <h3>FastAPI Backend</h3>
            <p>Upload, chat, health, metrics, auth-ready routes, logging, and validation.</p>
          </div>
          <div className="arch-services">
            <article>
              <Database size={24} />
              <strong>Pinecone / Chroma</strong>
              <span>Vector search</span>
            </article>
            <article>
              <GitBranch size={24} />
              <strong>LangChain</strong>
              <span>RAG orchestration</span>
            </article>
            <article>
              <Sparkles size={24} />
              <strong>OpenAI / LLaMA</strong>
              <span>Grounded generation</span>
            </article>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">Implementation modules</p>
          <h2>Production Deliverables</h2>
          <p>These are the concrete pieces employers and teams expect to see in a serious AI application.</p>
        </div>
        <div className="deliverable-grid">
          {deliverables.map(({ icon: Icon, title, text }) => (
            <article className="deliverable-card" key={title}>
              <Icon size={24} />
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="workbench" className="workbench-section">
        <div className="section-heading">
          <p className="eyebrow">Live application</p>
          <h2>Upload, Retrieve, Ask, Cite</h2>
          <p>This workbench connects to the FastAPI backend and demonstrates the RAG loop end to end.</p>
        </div>
        <div className="workbench">
          <aside className="sidebar" aria-label="Document manager">
            <div className="brand">
              <FileText size={28} />
              <div>
                <h3>Knowledge Base</h3>
                <p>{documents.length} docs | {totalChunks} chunks</p>
              </div>
            </div>

            <label className="upload-zone">
              <UploadCloud size={24} />
              <span>Upload documents</span>
              <small>TXT, MD, PDF, DOCX</small>
              <input
                type="file"
                multiple
                accept=".txt,.md,.markdown,.pdf,.docx"
                onChange={(event) => handleUpload(event.currentTarget.files)}
              />
            </label>

            <div className="metric-panel" aria-label="Runtime metrics">
              <Activity size={18} />
              <div>
                <strong>{metrics?.chats_served ?? 0} chats</strong>
                <span>{metrics?.average_latency_ms ?? 0}ms avg total | {metrics?.average_retrieval_ms ?? 0}ms retrieval</span>
              </div>
            </div>

            <div className="document-list">
              {documents.map((document) => (
                <article className="document-card" key={document.document_id}>
                  <div>
                    <strong>{document.title}</strong>
                    <span>{document.chunk_count} chunks | {document.character_count.toLocaleString()} chars</span>
                  </div>
                  <button type="button" onClick={() => handleDelete(document.document_id)} aria-label={`Delete ${document.title}`}>
                    <Trash2 size={16} />
                  </button>
                </article>
              ))}
              {!documents.length && <p className="empty">No documents indexed yet.</p>}
            </div>
          </aside>

          <section className="chat-panel" aria-label="RAG chat">
            <header className="chat-header">
              <div>
                <p>Grounded document Q&A</p>
                <h3>Ask your knowledge base</h3>
              </div>
              <label>
                Top K
                <input type="range" min="1" max="12" value={topK} onChange={(event) => setTopK(Number(event.target.value))} />
                <span>{topK}</span>
              </label>
            </header>

            <div className="messages">
              {messages.map((message, index) => (
                <article className={`message ${message.role}`} key={`${message.role}-${index}`}>
                  <div className="message-icon">
                    <MessageSquare size={16} />
                  </div>
                  <div>
                    <p>{message.content}</p>
                    {!!message.citations?.length && (
                      <div className="citations">
                        {message.citations.map((citation) => (
                          <details key={`${citation.document_id}-${citation.chunk_index}`}>
                            <summary>{citation.label} {citation.title} #{citation.chunk_index}</summary>
                            <p>{citation.excerpt}</p>
                          </details>
                        ))}
                      </div>
                    )}
                  </div>
                </article>
              ))}
            </div>

            {status && <div className="status">{status}</div>}

            <form className="composer" onSubmit={handleSubmit}>
              <input
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask about your uploaded documents..."
              />
              <button type="submit" disabled={busy || !question.trim()}>
                {busy ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
                <span>Ask</span>
              </button>
            </form>
          </section>
        </div>
      </section>

      <section className="section split-section">
        <div>
          <p className="eyebrow">Testing, deployment, hardening</p>
          <h2>Make It Interview-Ready and Team-Ready</h2>
          <p>
            Production value comes from the boring-but-crucial work: tests, CI, Docker, monitoring,
            rate limits, clear docs, feedback loops, and measurable quality.
          </p>
        </div>
        <div className="ops-grid">
          <article><Code2 size={20} /><span>Backend and frontend tests</span></article>
          <article><Gauge size={20} /><span>Latency below 2 seconds</span></article>
          <article><Lock size={20} /><span>Validation, auth, rate limits</span></article>
          <article><Cloud size={20} /><span>Docker and cloud deployment</span></article>
          <article><Activity size={20} /><span>Sentry, DataDog, dashboards</span></article>
          <article><Rocket size={20} /><span>CI/CD with deploy gates</span></article>
        </div>
      </section>

      <section id="resources" className="section resource-section">
        <div className="section-heading">
          <p className="eyebrow">Learning path</p>
          <h2>Resources, Variations, and Success Criteria</h2>
          <p>Use these links and project variants to shape the final portfolio story.</p>
        </div>
        <div className="resource-layout">
          <article className="resource-card">
            <BookOpen size={24} />
            <h3>Useful Links</h3>
            <div className="link-list">
              {resources.map(([label, href]) => (
                <a href={href} key={label} target="_blank" rel="noreferrer">{label}</a>
              ))}
            </div>
          </article>
          <article className="resource-card">
            <GraduationCap size={24} />
            <h3>Project Variations</h3>
            {variations.map(([title, text]) => (
              <p key={title}><strong>{title}:</strong> {text}</p>
            ))}
          </article>
          <article className="resource-card">
            <CheckCircle2 size={24} />
            <h3>Success Criteria</h3>
            <ul>
              {successCriteria.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </article>
          <article className="resource-card">
            <MessageSquare size={24} />
            <h3>Weekly Reflection</h3>
            <ul>
              {weeklyQuestions.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </article>
        </div>
      </section>
    </main>
  );
}

export default App;
