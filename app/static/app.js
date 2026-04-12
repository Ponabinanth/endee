const bootstrap = window.__BOOTSTRAP__ || {};

const state = {
  filters: bootstrap.filters || { departments: [], doc_types: [], audiences: [] },
  examples: bootstrap.examples || [],
  ready: Boolean(bootstrap.ready),
};

const els = {
  statusPill: document.getElementById("status-pill"),
  metricIndex: document.getElementById("metric-index"),
  metricBackend: document.getElementById("metric-backend"),
  metricModel: document.getElementById("metric-model"),
  metricCorpus: document.getElementById("metric-corpus"),
  metricChunks: document.getElementById("metric-chunks"),
  searchForm: document.getElementById("search-form"),
  answerForm: document.getElementById("answer-form"),
  uploadForm: document.getElementById("upload-form"),
  resultsList: document.getElementById("results-list"),
  relatedList: document.getElementById("related-list"),
  answerOutput: document.getElementById("answer-output"),
  resultsCount: document.getElementById("results-count"),
  toast: document.getElementById("toast"),
  examplePrompts: document.getElementById("example-prompts"),
  sampleQuestionButton: document.getElementById("sample-question-button"),
  refreshButton: document.getElementById("refresh-button"),
  clearSearchButton: document.getElementById("clear-search"),
  useSearchQueryButton: document.getElementById("use-search-query"),
  searchQuery: document.getElementById("search-query"),
  answerQuestion: document.getElementById("answer-question"),
  searchTopK: document.getElementById("search-top-k"),
  answerTopK: document.getElementById("answer-top-k"),
  searchTopKValue: document.getElementById("search-top-k-value"),
  answerTopKValue: document.getElementById("answer-top-k-value"),
};

const selectIds = {
  searchDepartment: "search-department",
  searchDocType: "search-doc-type",
  searchAudience: "search-audience",
  answerDepartment: "answer-department",
  answerDocType: "answer-doc-type",
  answerAudience: "answer-audience",
  uploadDepartment: "upload-department",
  uploadDocType: "upload-doc-type",
  uploadAudience: "upload-audience",
};

function qs(id) {
  return document.getElementById(id);
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatScore(score) {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return "Score unavailable";
  }
  return `Similarity ${score.toFixed(3)}`;
}

function showToast(message, kind = "success") {
  els.toast.textContent = message;
  els.toast.className = `toast show ${kind}`;
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => {
    els.toast.className = "toast";
  }, 3000);
}

function setStatus(status) {
  state.ready = Boolean(status.ready);
  els.metricIndex.textContent = status.index_name || "n/a";
  els.metricBackend.textContent = status.embedding_backend || "n/a";
  els.metricModel.textContent = status.embedding_model || "n/a";
  els.metricCorpus.textContent = status.sample_documents ?? 0;
  els.metricChunks.textContent = status.sample_chunks ?? 0;

  els.statusPill.className = "status-pill";
  if (state.ready) {
    els.statusPill.classList.add("status-ready");
    els.statusPill.textContent = "Endee is online and the corpus is indexed.";
  } else if (status.error) {
    els.statusPill.classList.add("status-error");
    els.statusPill.textContent = `Endee bootstrap issue: ${status.error}`;
  } else {
    els.statusPill.classList.add("status-pending");
    els.statusPill.textContent = "Checking Endee...";
  }
}

function populateSelect(selectId, values) {
  const select = qs(selectId);
  select.innerHTML = "";
  const options = ["all", ...values];
  for (const value of options) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value === "all" ? "All" : value.replace(/(^|\s)\S/g, (match) => match.toUpperCase());
    select.appendChild(option);
  }
}

function initFilters(filters) {
  populateSelect(selectIds.searchDepartment, filters.departments || []);
  populateSelect(selectIds.searchDocType, filters.doc_types || []);
  populateSelect(selectIds.searchAudience, filters.audiences || []);
  populateSelect(selectIds.answerDepartment, filters.departments || []);
  populateSelect(selectIds.answerDocType, filters.doc_types || []);
  populateSelect(selectIds.answerAudience, filters.audiences || []);
  populateSelect(selectIds.uploadDepartment, filters.departments || []);
  populateSelect(selectIds.uploadDocType, filters.doc_types || []);
  populateSelect(selectIds.uploadAudience, filters.audiences || []);

  const defaultDepartment = (filters.departments || [])[0] || "all";
  const defaultDocType = (filters.doc_types || [])[0] || "all";
  const defaultAudience = (filters.audiences || [])[0] || "all";
  qs(selectIds.searchDepartment).value = "all";
  qs(selectIds.searchDocType).value = "all";
  qs(selectIds.searchAudience).value = "all";
  qs(selectIds.answerDepartment).value = "all";
  qs(selectIds.answerDocType).value = "all";
  qs(selectIds.answerAudience).value = "all";
  qs(selectIds.uploadDepartment).value = defaultDepartment;
  qs(selectIds.uploadDocType).value = defaultDocType;
  qs(selectIds.uploadAudience).value = defaultAudience;
}

function readFilterValues(prefix) {
  return {
    department: qs(`${prefix}-department`).value,
    doc_type: qs(`${prefix}-doc-type`).value,
    audience: qs(`${prefix}-audience`).value,
  };
}

function topKValue(prefix) {
  return Number(qs(`${prefix}-top-k`).value);
}

function renderPromptChips(prompts) {
  els.examplePrompts.innerHTML = "";
  for (const prompt of prompts) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "prompt-chip";
    button.textContent = prompt;
    button.addEventListener("click", () => {
      els.searchQuery.value = prompt;
      els.answerQuestion.value = prompt;
      els.searchQuery.focus();
    });
    els.examplePrompts.appendChild(button);
  }
}

function renderEmpty(target, message) {
  target.classList.add("empty-state");
  target.textContent = message;
}

function renderResults(results, target, { related = false } = {}) {
  target.classList.remove("empty-state");
  target.innerHTML = "";

  if (!results.length) {
    renderEmpty(
      target,
      related ? "No related passages matched these filters." : "No passages matched this search."
    );
    return;
  }

  for (const result of results) {
    const card = document.createElement("article");
    card.className = "result-card";
    card.innerHTML = `
      <div class="result-top">
        <div>
          <h3 class="result-title">${escapeHtml(result.title)}</h3>
          <div class="result-meta">
            <span class="chip">${escapeHtml(result.department || "n/a")}</span>
            <span class="chip">${escapeHtml(result.doc_type || "n/a")}</span>
            <span class="chip">${escapeHtml(result.audience || "n/a")}</span>
            <span class="chip">${escapeHtml(result.source || "n/a")}</span>
          </div>
        </div>
        <span class="result-score">${escapeHtml(formatScore(result.score))}</span>
      </div>
      <p class="result-excerpt">${escapeHtml(result.excerpt || result.text || "")}</p>
      <div class="card-actions">
        <button type="button" class="button button-secondary" data-related-text="${escapeHtml(result.text || "")}">
          Find related
        </button>
      </div>
    `;

    const relatedButton = card.querySelector("[data-related-text]");
    relatedButton.addEventListener("click", async () => {
      try {
        await requestRelated(result.text || "", readFilterValues("search"), topKValue("search"));
      } catch (error) {
        showToast(error.message, "error");
      }
    });

    target.appendChild(card);
  }
}

function renderAnswer(payload) {
  const citations = payload.citations || [];
  const citationMarkup = citations.length
    ? `
      <div class="chip-row" style="margin-top: 14px;">
        ${citations
          .map(
            (citation) => `
              <span class="chip">
                ${escapeHtml(citation.label)} ${escapeHtml(citation.title)}
              </span>
            `
          )
          .join("")}
      </div>
    `
    : "";

  els.answerOutput.classList.remove("empty-state");
  els.answerOutput.innerHTML = `
    <div class="chip-row">
      <span class="chip">Mode: ${escapeHtml(payload.mode)}</span>
      <span class="chip">Filters: ${escapeHtml(payload.filters?.department || "all")} / ${escapeHtml(payload.filters?.doc_type || "all")} / ${escapeHtml(payload.filters?.audience || "all")}</span>
    </div>
    <pre style="white-space: pre-wrap; margin: 14px 0 0; font: inherit;">${escapeHtml(payload.answer || "")}</pre>
    ${citationMarkup}
  `;
}

function renderCitationPanel(results) {
  if (!results.length) {
    renderEmpty(els.relatedList, "Select a result to find similar passages.");
    return;
  }
  renderResults(results, els.relatedList, { related: true });
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const message = payload?.detail?.message || payload?.detail || response.statusText;
    throw new Error(message || "Request failed");
  }
  return response.json();
}

async function requestSearch() {
  const query = els.searchQuery.value.trim();
  if (!query) {
    showToast("Type a search query first.", "error");
    return;
  }

  const body = {
    query,
    ...readFilterValues("search"),
    top_k: topKValue("search"),
  };

  const payload = await postJson("/api/search", body);
  els.resultsCount.textContent = `${payload.results.length} result${payload.results.length === 1 ? "" : "s"}`;
  renderResults(payload.results, els.resultsList);
  showToast(`Found ${payload.results.length} relevant chunks.`);
}

async function requestAnswer() {
  const question = els.answerQuestion.value.trim();
  if (!question) {
    showToast("Type a question first.", "error");
    return;
  }

  const body = {
    question,
    ...readFilterValues("answer"),
    top_k: topKValue("answer"),
  };

  const payload = await postJson("/api/answer", body);
  renderAnswer(payload);
  showToast(`Generated a ${payload.mode} answer.`);
}

async function requestRelated(text, filterValues, topK) {
  if (!text) {
    showToast("No text was available for similarity search.", "error");
    return;
  }
  const payload = await postJson("/api/related", {
    text,
    ...filterValues,
    top_k: topK,
  });
  renderCitationPanel(payload.results);
  showToast(`Loaded ${payload.results.length} related passages.`);
}

async function uploadKnowledge(event) {
  event.preventDefault();
  const files = document.getElementById("upload-files").files;
  if (!files.length) {
    showToast("Choose one or more .txt or .md files.", "error");
    return;
  }

  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  formData.append("title", document.getElementById("upload-title").value || "");
  formData.append("department", document.getElementById("upload-department").value);
  formData.append("doc_type", document.getElementById("upload-doc-type").value);
  formData.append("audience", document.getElementById("upload-audience").value);
  formData.append("source_prefix", document.getElementById("upload-source-prefix").value || "uploads");

  const response = await fetch("/api/upload", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload?.detail || response.statusText);
  }

  const payload = await response.json();
  showToast(`${payload.message} (${payload.uploaded_chunks} new chunks)`);
}

async function refreshStatus() {
  const response = await fetch("/api/status");
  const status = await response.json();
  state.filters = status.filters || state.filters;
  state.examples = status.examples || state.examples;
  setStatus(status);
  initFilters(state.filters);
  renderPromptChips(state.examples);
}

function wireRangeCounter(rangeId, outputId) {
  const range = qs(rangeId);
  const output = qs(outputId);
  const sync = () => {
    output.textContent = range.value;
  };
  range.addEventListener("input", sync);
  sync();
}

function initFromBootstrap() {
  setStatus(bootstrap);
  initFilters(state.filters);
  renderPromptChips(state.examples);
  wireRangeCounter("search-top-k", "search-top-k-value");
  wireRangeCounter("answer-top-k", "answer-top-k-value");

  const firstPrompt = state.examples[0] || "What is the rollback process for a production release?";
  els.searchQuery.value = firstPrompt;
  els.answerQuestion.value = firstPrompt;

  if (state.examples.length) {
    showToast("Sample prompts loaded.");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initFromBootstrap();

  els.searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await requestSearch();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.answerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await requestAnswer();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await uploadKnowledge(event);
      await refreshStatus();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.sampleQuestionButton.addEventListener("click", () => {
    const prompt = state.examples[0] || "What is the rollback process for a production release?";
    els.searchQuery.value = prompt;
    els.answerQuestion.value = prompt;
    els.answerQuestion.focus();
    showToast("Loaded a sample question.");
  });

  els.refreshButton.addEventListener("click", async () => {
    try {
      await refreshStatus();
      showToast("Status refreshed.");
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.clearSearchButton.addEventListener("click", () => {
    els.searchQuery.value = "";
    els.resultsList.innerHTML = "";
    renderEmpty(els.resultsList, "Run a search to surface the most relevant chunks from Endee.");
    els.resultsCount.textContent = "0 results";
  });

  els.useSearchQueryButton.addEventListener("click", () => {
    els.answerQuestion.value = els.searchQuery.value || els.answerQuestion.value;
    showToast("Copied the search query into the answer box.");
  });

  els.searchQuery.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      els.searchForm.requestSubmit();
    }
  });
});
