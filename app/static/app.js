const bootstrap = window.__BOOTSTRAP__ || {};

const state = {
  filters: bootstrap.filters || { roles: [], locations: [], stages: [], skills: [] },
  examples: bootstrap.examples || [],
  ready: Boolean(bootstrap.ready),
  candidates: [],
  jobs: [],
  selectedCandidateId: "",
  selectedJobId: "",
  currentQuestions: [],
  interviewActive: false,
  telemetry: {
    tab_switches: 0,
    copy_events: 0,
    paste_events: 0,
    blur_events: 0,
    idle_seconds: 0,
    multiple_faces_detected: false,
  },
  lastActivityAt: Date.now(),
  lastFraudResult: null,
};

const STORAGE_KEYS = {
  candidates: "hirepilot.candidates.v1",
  jobs: "hirepilot.jobs.v1",
};

const els = {
  statusPill: document.getElementById("status-pill"),
  metricVector: document.getElementById("metric-vector"),
  metricBackend: document.getElementById("metric-backend"),
  metricModel: document.getElementById("metric-model"),
  metricCandidates: document.getElementById("metric-candidates"),
  metricJobs: document.getElementById("metric-jobs"),
  searchForm: document.getElementById("search-form"),
  answerForm: document.getElementById("answer-form"),
  uploadForm: document.getElementById("upload-form"),
  jobForm: document.getElementById("job-form"),
  searchResults: document.getElementById("search-results"),
  relatedResults: document.getElementById("related-results"),
  rankResults: document.getElementById("rank-results"),
  answerOutput: document.getElementById("answer-output"),
  feedbackOutput: document.getElementById("feedback-output"),
  interviewQuestions: document.getElementById("interview-questions"),
  interviewResult: document.getElementById("interview-result"),
  telemetryPanel: document.getElementById("telemetry-panel"),
  resultsCount: document.getElementById("results-count"),
  toast: document.getElementById("toast"),
  examplePrompts: document.getElementById("example-prompts"),
  samplePromptButton: document.getElementById("sample-prompt-button"),
  refreshButton: document.getElementById("refresh-button"),
  resetSessionButton: document.getElementById("reset-session-button"),
  clearSearchButton: document.getElementById("clear-search"),
  useSearchQueryButton: document.getElementById("use-search-query"),
  searchQuery: document.getElementById("search-query"),
  answerQuestion: document.getElementById("answer-question"),
  searchTopK: document.getElementById("search-top-k"),
  answerTopK: document.getElementById("answer-top-k"),
  interviewCount: document.getElementById("interview-count"),
  searchTopKValue: document.getElementById("search-top-k-value"),
  answerTopKValue: document.getElementById("answer-top-k-value"),
  interviewCountValue: document.getElementById("interview-count-value"),
  multipleFaces: document.getElementById("multiple-faces"),
  uploadFiles: document.getElementById("upload-files"),
  candidateName: document.getElementById("candidate-name"),
  candidateTargetRole: document.getElementById("candidate-target-role"),
  candidateYears: document.getElementById("candidate-years"),
  candidateLocation: document.getElementById("candidate-location"),
  candidateSkills: document.getElementById("candidate-skills"),
  candidateStage: document.getElementById("candidate-stage"),
  uploadSourcePrefix: document.getElementById("upload-source-prefix"),
  jobTitle: document.getElementById("job-title"),
  jobDepartment: document.getElementById("job-department"),
  jobLocation: document.getElementById("job-location"),
  jobMinYears: document.getElementById("job-min-years"),
  jobDescription: document.getElementById("job-description"),
  jobMustHave: document.getElementById("job-must-have"),
  jobNiceHave: document.getElementById("job-nice-to-have"),
  jobFocus: document.getElementById("job-focus"),
  createJobButton: document.getElementById("create-job-button"),
  rankButton: document.getElementById("rank-button"),
  generateInterviewButton: document.getElementById("generate-interview-button"),
  evaluateInterviewButton: document.getElementById("evaluate-interview-button"),
  resumeFeedbackButton: document.getElementById("resume-feedback-button"),
  fraudCheckButton: document.getElementById("fraud-check-button"),
  resetInterviewButton: document.getElementById("reset-interview-button"),
  interviewCandidate: document.getElementById("interview-candidate"),
  interviewJob: document.getElementById("interview-job"),
  searchRole: document.getElementById("search-role"),
  searchLocation: document.getElementById("search-location"),
  searchStage: document.getElementById("search-stage"),
  answerRole: document.getElementById("answer-role"),
  answerLocation: document.getElementById("answer-location"),
  answerStage: document.getElementById("answer-stage"),
};

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function humanize(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/(^|\s)\S/g, (match) => match.toUpperCase());
}

function showToast(message, kind = "success") {
  els.toast.textContent = message;
  els.toast.className = `toast show ${kind}`;
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => {
    els.toast.className = "toast";
  }, 3200);
}

function clampNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function splitList(value) {
  return String(value || "")
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function loadFromStorage(key, fallback = []) {
  try {
    const raw = window.localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : fallback;
    return Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function saveToStorage(key, value) {
  window.localStorage.setItem(key, JSON.stringify(value));
}

function upsertById(list, item, idKey) {
  const id = item?.[idKey];
  if (!id) {
    return list;
  }
  const existingIndex = list.findIndex((entry) => entry?.[idKey] === id);
  if (existingIndex === -1) {
    return [item, ...list];
  }
  const next = [...list];
  next[existingIndex] = { ...next[existingIndex], ...item };
  return next;
}

function setStatus(status) {
  state.ready = Boolean(status.ready);
  els.metricVector.textContent = status.vector_store_backend || "n/a";
  els.metricBackend.textContent = status.embedding_backend || "n/a";
  els.metricModel.textContent = status.embedding_model || "n/a";
  els.metricCandidates.textContent = status.sample_candidates ?? 0;
  els.metricJobs.textContent = status.sample_jobs ?? 0;

  els.statusPill.className = "status-pill";
  if (state.ready) {
    els.statusPill.classList.add("status-ready");
    els.statusPill.textContent = "Vector store online and hiring corpus indexed.";
  } else if (status.error) {
    els.statusPill.classList.add("status-error");
    els.statusPill.textContent = `Bootstrap issue: ${status.error}`;
  } else {
    els.statusPill.classList.add("status-pending");
    els.statusPill.textContent = "Checking vector store...";
  }
}

function populateSelect(select, values, { includeAll = true, placeholder = "Select..." } = {}) {
  const currentValue = select.value;
  select.innerHTML = "";

  if (includeAll) {
    const allOption = document.createElement("option");
    allOption.value = "all";
    allOption.textContent = "All";
    select.appendChild(allOption);
  } else if (placeholder) {
    const placeholderOption = document.createElement("option");
    placeholderOption.value = "";
    placeholderOption.textContent = placeholder;
    select.appendChild(placeholderOption);
  }

  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = humanize(value);
    select.appendChild(option);
  }

  if (currentValue && [...select.options].some((option) => option.value === currentValue)) {
    select.value = currentValue;
  } else if (!includeAll && values.length) {
    select.value = values[0];
  } else {
    select.value = includeAll ? "all" : "";
  }
}

function populateFilterSelects(filters) {
  populateSelect(els.searchRole, filters.roles || []);
  populateSelect(els.searchLocation, filters.locations || []);
  populateSelect(els.searchStage, filters.stages || []);
  populateSelect(els.answerRole, filters.roles || []);
  populateSelect(els.answerLocation, filters.locations || []);
  populateSelect(els.answerStage, filters.stages || []);
  populateSelect(els.candidateStage, filters.stages || ["screening", "interview", "assessment", "final"], {
    includeAll: false,
    placeholder: "screening",
  });
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
  target.innerHTML = `<p class="empty-copy">${escapeHtml(message)}</p>`;
}

function formatSimilarity(result, kind) {
  if (kind === "rank") {
    return result.match_label || `Match ${clampNumber(result.overall_score, 0).toFixed(1)}/100`;
  }
  return result.similarity_label || `Similarity ${clampNumber(result.score, 0).toFixed(3)}`;
}

function renderScoreBreakdown(breakdown) {
  if (!breakdown) {
    return "";
  }
  return `
    <div class="chip-row score-row">
      <span class="chip">Semantic ${Number(breakdown.semantic || 0).toFixed(1)}</span>
      <span class="chip">Skills ${Number(breakdown.skills || 0).toFixed(1)}</span>
      <span class="chip">Experience ${Number(breakdown.experience || 0).toFixed(1)}</span>
      <span class="chip">Location ${Number(breakdown.location || 0).toFixed(1)}</span>
    </div>
  `;
}

function renderReasons(reasons) {
  if (!reasons || !reasons.length) {
    return "";
  }
  return `
    <ul class="reason-list">
      ${reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}
    </ul>
  `;
}

function selectCandidate(id, { silent = false } = {}) {
  state.selectedCandidateId = id || "";
  if (els.interviewCandidate && id) {
    els.interviewCandidate.value = id;
  }
  if (!silent) {
    showToast("Candidate selected for interview and feedback.");
  }
}

function selectJob(id, { silent = false } = {}) {
  state.selectedJobId = id || "";
  if (els.interviewJob && id) {
    els.interviewJob.value = id;
  }
  if (!silent) {
    showToast("Job selected for interview and feedback.");
  }
}

function getSelectedCandidate() {
  const candidateId = state.selectedCandidateId || els.interviewCandidate.value;
  return state.candidates.find((candidate) => (candidate.candidate_id || candidate.id) === candidateId) || state.candidates[0] || null;
}

function getSelectedJob() {
  const jobId = state.selectedJobId || els.interviewJob.value;
  return state.jobs.find((job) => (job.job_id || job.id) === jobId) || state.jobs[0] || null;
}

function candidateSnapshotFromResult(result) {
  return {
    candidate_id: result.id,
    name: result.name,
    headline: result.headline || "",
    target_role: result.target_role || "",
    years_experience: clampNumber(result.years_experience, 0),
    location: result.location || "",
    skills: result.skills || [],
    resume_text: result.text || result.excerpt || "",
    source: result.source || "",
    stage: "screening",
  };
}

function candidateSnapshotFromState(candidate) {
  if (!candidate) {
    return null;
  }
  return {
    candidate_id: candidate.candidate_id || candidate.id,
    name: candidate.name,
    headline: candidate.headline || "",
    target_role: candidate.target_role || "",
    years_experience: clampNumber(candidate.years_experience, 0),
    location: candidate.location || "",
    skills: candidate.skills || [],
    resume_text: candidate.resume_text || candidate.text || "",
    source: candidate.source || "",
    stage: candidate.stage || "screening",
  };
}

function jobSnapshotFromState(job) {
  if (!job) {
    return null;
  }
  return {
    job_id: job.job_id || job.id,
    title: job.title,
    description: job.description || "",
    department: job.department || "engineering",
    location: job.location || "Remote",
    min_years_experience: clampNumber(job.min_years_experience, 0),
    must_have_skills: job.must_have_skills || [],
    nice_to_have_skills: job.nice_to_have_skills || [],
    interview_focus: job.interview_focus || [],
  };
}

function jobSnapshotFromForm() {
  return {
    job_id: null,
    title: els.jobTitle.value.trim() || "Untitled Role",
    description: els.jobDescription.value.trim() || "Role description not provided.",
    department: els.jobDepartment.value.trim() || "engineering",
    location: els.jobLocation.value.trim() || "Remote",
    min_years_experience: clampNumber(els.jobMinYears.value, 0),
    must_have_skills: splitList(els.jobMustHave.value),
    nice_to_have_skills: splitList(els.jobNiceHave.value),
    interview_focus: splitList(els.jobFocus.value),
  };
}

function renderCandidateCards(results, target, { kind = "search" } = {}) {
  target.classList.remove("empty-state");
  target.innerHTML = "";

  if (!results.length) {
    renderEmpty(
      target,
      kind === "related"
        ? "No similar candidates matched this profile."
        : kind === "rank"
          ? "No candidates matched this role yet."
          : "No candidates matched this search."
    );
    return;
  }

  for (const result of results) {
    const card = document.createElement("article");
    card.className = "result-card";
    const scoreLabel = formatSimilarity(result, kind);
    const scoreClass = kind === "rank" ? "result-score result-score-rank" : "result-score";
    card.innerHTML = `
      <div class="result-top">
        <div>
          <h3 class="result-title">${escapeHtml(result.name || result.title || "Untitled candidate")}</h3>
          <p class="result-subtitle">${escapeHtml(result.headline || result.excerpt || "")}</p>
          <div class="result-meta">
            <span class="chip">${escapeHtml(result.target_role || "n/a")}</span>
            <span class="chip">${escapeHtml(result.location || "n/a")}</span>
            <span class="chip">${escapeHtml(Number(result.years_experience || 0).toFixed(1))} yrs</span>
            <span class="chip">${escapeHtml((result.skills || []).slice(0, 4).join(", ") || "skills n/a")}</span>
          </div>
        </div>
        <span class="${scoreClass}">${escapeHtml(scoreLabel)}</span>
      </div>
      <p class="result-excerpt">${escapeHtml(result.excerpt || result.text || "")}</p>
      ${kind === "rank" ? renderScoreBreakdown(result.score_breakdown) : ""}
      ${renderReasons(result.reasons)}
      <div class="card-actions">
        <button type="button" class="button button-secondary" data-action="select">Use in interview</button>
        <button type="button" class="button button-secondary" data-action="related">Find related</button>
        <button type="button" class="button button-ghost" data-action="feedback">Resume feedback</button>
      </div>
    `;

    card.querySelector('[data-action="select"]').addEventListener("click", () => {
      const snapshot = candidateSnapshotFromResult(result);
      state.candidates = upsertById(state.candidates, snapshot, "candidate_id");
      saveToStorage(STORAGE_KEYS.candidates, state.candidates);
      // Keep the interview dropdowns in sync with what we just selected.
      refreshEntities();
      selectCandidate(result.id);
      showToast(`${result.name} selected.`);
    });

    card.querySelector('[data-action="related"]').addEventListener("click", async () => {
      try {
        await requestRelated(result.text || "", readFilterValues("search"), topKValue("search"));
      } catch (error) {
        showToast(error.message, "error");
      }
    });

    card.querySelector('[data-action="feedback"]').addEventListener("click", async () => {
      try {
        await requestResumeFeedback(candidateSnapshotFromResult(result), jobSnapshotFromState(getSelectedJob()) || jobSnapshotFromForm());
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
      <div class="chip-row citation-row">
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
      <span class="chip">Filters: ${escapeHtml(payload.filters?.role || "all")} / ${escapeHtml(payload.filters?.location || "all")} / ${escapeHtml(payload.filters?.stage || "all")}</span>
    </div>
    <pre class="output-pre">${escapeHtml(payload.answer || "")}</pre>
    ${citationMarkup}
  `;
}

function renderFeedback(payload) {
  els.feedbackOutput.classList.remove("empty-state");
  els.feedbackOutput.innerHTML = `
    <div class="chip-row">
      <span class="chip">Resume feedback</span>
      <span class="chip">${escapeHtml(payload.job?.title || "Selected role")}</span>
      <span class="chip">${escapeHtml(payload.candidate?.name || "Selected candidate")}</span>
    </div>
    <p class="insight-summary">${escapeHtml(payload.summary || "")}</p>
    <div class="chip-row">
      ${((payload.missing_skills || [])).map((skill) => `<span class="chip chip-warning">Missing ${escapeHtml(skill)}</span>`).join("")}
    </div>
    <ul class="bullet-list">
      ${(payload.suggestions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
  `;
}

function renderInterviewQuestions(payload) {
  state.currentQuestions = payload.questions || [];
  state.interviewActive = true;
  state.telemetry.idle_seconds = 0;
  state.lastActivityAt = Date.now();
  els.multipleFaces.checked = false;
  state.telemetry.multiple_faces_detected = false;

  els.interviewQuestions.classList.remove("empty-state");
  els.interviewQuestions.innerHTML = `
    <div class="chip-row">
      <span class="chip">Candidate: ${escapeHtml(payload.candidate?.name || "Selected candidate")}</span>
      <span class="chip">Job: ${escapeHtml(payload.job?.title || "Selected role")}</span>
      <span class="chip">Rubric: technical / communication / confidence / fraud</span>
    </div>
    <div class="question-list-inner">
      ${(payload.questions || [])
        .map(
          (question, index) => `
            <article class="question-card">
              <div class="question-head">
                <div>
                  <span class="question-index">Q${index + 1}</span>
                  <h3>${escapeHtml(question.question)}</h3>
                </div>
                <span class="chip">${escapeHtml(question.difficulty || "core")}</span>
              </div>
              <div class="chip-row">
                <span class="chip">${escapeHtml(question.focus || "focus")}</span>
                <span class="chip">${escapeHtml(question.expected_signal || "expected signal")}</span>
              </div>
              <label class="field">
                <span>Your answer</span>
                <textarea id="answer-${index}" data-question="${escapeHtml(question.question)}" rows="4" placeholder="Type the candidate response here..."></textarea>
              </label>
            </article>
          `
        )
        .join("")}
    </div>
  `;

  renderTelemetryPanel();
}

function renderInterviewResult(payload) {
  els.interviewResult.classList.remove("empty-state");
  els.interviewResult.innerHTML = `
    <div class="chip-row">
      <span class="chip">Overall ${escapeHtml(Number(payload.overall_score || 0).toFixed(1))}</span>
      <span class="chip">Technical ${escapeHtml(Number(payload.technical_score || 0).toFixed(1))}</span>
      <span class="chip">Communication ${escapeHtml(Number(payload.communication_score || 0).toFixed(1))}</span>
      <span class="chip">Confidence ${escapeHtml(Number(payload.confidence_score || 0).toFixed(1))}</span>
      <span class="chip ${payload.fraud_score >= 60 ? "chip-warning" : ""}">Fraud risk ${escapeHtml(Number(payload.fraud_score || 0).toFixed(1))}</span>
    </div>
    <ul class="bullet-list">
      ${(payload.reasons || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
    ${payload.fraud_flags?.length ? `<div class="chip-row">${payload.fraud_flags.map((flag) => `<span class="chip chip-warning">${escapeHtml(flag)}</span>`).join("")}</div>` : ""}
    <div class="chip-row">
      ${(payload.suggestions || []).map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("")}
    </div>
  `;
  state.lastFraudResult = payload;
  renderTelemetryPanel();
}

function renderFraudResult(payload) {
  const labelClass = payload.label === "high" ? "chip-warning" : "";
  els.interviewResult.classList.remove("empty-state");
  els.interviewResult.innerHTML = `
    <div class="chip-row">
      <span class="chip ${labelClass}">Fraud score ${escapeHtml(Number(payload.fraud_score || 0).toFixed(1))}</span>
      <span class="chip">Risk label ${escapeHtml(payload.label)}</span>
    </div>
    <ul class="bullet-list">
      ${(payload.flags || []).map((flag) => `<li>${escapeHtml(flag)}</li>`).join("") || "<li>No major fraud signals were detected.</li>"}
    </ul>
  `;
  state.lastFraudResult = payload;
  renderTelemetryPanel();
}

function renderTelemetryPanel() {
  const telemetry = state.telemetry;
  const lastRisk = state.lastFraudResult && typeof state.lastFraudResult.fraud_score === "number"
    ? Number(state.lastFraudResult.fraud_score).toFixed(1)
    : "n/a";
  els.telemetryPanel.innerHTML = `
    <div class="telemetry-card">
      <span class="metric-label">Tab switches</span>
      <strong>${telemetry.tab_switches}</strong>
    </div>
    <div class="telemetry-card">
      <span class="metric-label">Copy / paste</span>
      <strong>${telemetry.copy_events} / ${telemetry.paste_events}</strong>
    </div>
    <div class="telemetry-card">
      <span class="metric-label">Blur events</span>
      <strong>${telemetry.blur_events}</strong>
    </div>
    <div class="telemetry-card">
      <span class="metric-label">Idle seconds</span>
      <strong>${Math.max(0, Math.round(telemetry.idle_seconds))}</strong>
    </div>
    <div class="telemetry-card">
      <span class="metric-label">Multiple faces</span>
      <strong>${telemetry.multiple_faces_detected ? "flagged" : "clear"}</strong>
    </div>
    <div class="telemetry-card">
      <span class="metric-label">Last fraud check</span>
      <strong>${lastRisk}</strong>
    </div>
  `;
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

function readFilterValues(prefix) {
  return {
    role: els[`${prefix}Role`].value,
    location: els[`${prefix}Location`].value,
    stage: els[`${prefix}Stage`].value,
  };
}

function topKValue(prefix) {
  return Number(els[`${prefix}TopK`].value);
}

function wireRangeCounter(rangeId, outputId) {
  const range = document.getElementById(rangeId);
  const output = document.getElementById(outputId);
  const sync = () => {
    output.textContent = range.value;
  };
  range.addEventListener("input", sync);
  sync();
}

function resetSearchResults() {
  els.searchResults.innerHTML = "";
  renderEmpty(els.searchResults, "Run a search to surface the most relevant candidates.");
  els.relatedResults.innerHTML = "";
  renderEmpty(els.relatedResults, "Select a candidate to find similar resumes.");
  els.rankResults.innerHTML = "";
  renderEmpty(els.rankResults, "Rank a role to see explainable candidate scores.");
  els.resultsCount.textContent = "0 results";
}

function resetInterviewSession() {
  state.currentQuestions = [];
  state.interviewActive = false;
  state.telemetry = {
    tab_switches: 0,
    copy_events: 0,
    paste_events: 0,
    blur_events: 0,
    idle_seconds: 0,
    multiple_faces_detected: false,
  };
  state.lastActivityAt = Date.now();
  state.lastFraudResult = null;
  els.multipleFaces.checked = false;
  renderTelemetryPanel();
  renderEmpty(els.interviewQuestions, "Generate interview questions to unlock adaptive scoring.");
  renderEmpty(els.interviewResult, "Interview scores and fraud signals will appear here.");
}

async function refreshStatus() {
  const response = await fetch("/api/status");
  if (!response.ok) {
    throw new Error("Could not refresh status.");
  }
  const status = await response.json();
  state.filters = status.filters || state.filters;
  state.examples = status.examples || state.examples;
  setStatus(status);
  populateFilterSelects(state.filters);
  renderPromptChips(state.examples);
}

async function refreshEntities() {
  state.candidates = loadFromStorage(STORAGE_KEYS.candidates, []);
  state.jobs = loadFromStorage(STORAGE_KEYS.jobs, []);

  if (!state.jobs.length) {
    const seed = jobSnapshotFromForm();
    seed.job_id = seed.job_id || `job_${Math.random().toString(16).slice(2)}`;
    state.jobs = [seed];
    saveToStorage(STORAGE_KEYS.jobs, state.jobs);
  }

  const previousCandidate = state.selectedCandidateId || els.interviewCandidate.value;
  const previousJob = state.selectedJobId || els.interviewJob.value;

  els.interviewCandidate.innerHTML = "";
  if (!state.candidates.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No candidates yet (upload or search)";
    els.interviewCandidate.appendChild(option);
  } else {
    for (const candidate of state.candidates) {
      const option = document.createElement("option");
      option.value = candidate.candidate_id || candidate.id;
      option.textContent = `${candidate.name} | ${candidate.target_role || candidate.headline || "Candidate"}`;
      els.interviewCandidate.appendChild(option);
    }
  }

  els.interviewJob.innerHTML = "";
  for (const job of state.jobs) {
    const option = document.createElement("option");
    option.value = job.job_id || job.id;
    option.textContent = `${job.title} | ${job.location}`;
    els.interviewJob.appendChild(option);
  }

  if (previousCandidate && [...els.interviewCandidate.options].some((option) => option.value === previousCandidate)) {
    els.interviewCandidate.value = previousCandidate;
  } else if (state.candidates.length) {
    els.interviewCandidate.value = state.candidates[0].candidate_id || state.candidates[0].id;
  } else {
    els.interviewCandidate.value = "";
  }

  if (previousJob && [...els.interviewJob.options].some((option) => option.value === previousJob)) {
    els.interviewJob.value = previousJob;
  } else if (state.jobs.length) {
    els.interviewJob.value = state.jobs[0].job_id || state.jobs[0].id;
  }

  state.selectedCandidateId = els.interviewCandidate.value || "";
  state.selectedJobId = els.interviewJob.value || "";
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
  state.candidates = (payload.results || []).reduce((acc, result) => {
    return upsertById(acc, candidateSnapshotFromResult(result), "candidate_id");
  }, state.candidates);
  saveToStorage(STORAGE_KEYS.candidates, state.candidates);
  refreshEntities();
  els.resultsCount.textContent = `${payload.results.length} result${payload.results.length === 1 ? "" : "s"}`;
  renderCandidateCards(payload.results, els.searchResults, { kind: "search" });
  showToast(`Found ${payload.results.length} candidate matches.`);
}

async function requestAnswer() {
  const question = els.answerQuestion.value.trim();
  if (!question) {
    showToast("Type a recruiter question first.", "error");
    return;
  }

  const body = {
    question,
    ...readFilterValues("answer"),
    top_k: topKValue("answer"),
  };

  const payload = await postJson("/api/answer", body);
  renderAnswer(payload);
  showToast(`Generated a ${payload.mode} explanation.`);
}

async function requestRelated(text, filters, topK) {
  if (!text) {
    showToast("No resume text was available for similarity search.", "error");
    return;
  }
  const payload = await postJson("/api/related", {
    text,
    ...filters,
    top_k: topK,
  });
  state.candidates = (payload.results || []).reduce((acc, result) => {
    return upsertById(acc, candidateSnapshotFromResult(result), "candidate_id");
  }, state.candidates);
  saveToStorage(STORAGE_KEYS.candidates, state.candidates);
  refreshEntities();
  renderCandidateCards(payload.results, els.relatedResults, { kind: "related" });
  showToast(`Loaded ${payload.results.length} related profiles.`);
}

async function uploadResume(event) {
  event.preventDefault();
  const files = els.uploadFiles.files;
  if (!files.length) {
    showToast("Choose one or more .txt or .md files.", "error");
    return;
  }

  const fileTexts = await Promise.all(
    Array.from(files).map(async (file) => {
      try {
        return await file.text();
      } catch {
        return "";
      }
    })
  );

  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  formData.append("name", els.candidateName.value || "");
  formData.append("target_role", els.candidateTargetRole.value || "AI Engineer");
  formData.append("location", els.candidateLocation.value || "Remote");
  formData.append("stage", els.candidateStage.value || "screening");
  formData.append("source_prefix", els.uploadSourcePrefix.value || "candidates");

  // Backwards-compatible fields (backend accepts them too).
  formData.append("title", "");
  formData.append("department", els.candidateTargetRole.value || "all");
  formData.append("doc_type", "candidate_resume");
  formData.append("audience", els.candidateStage.value || "screening");

  const response = await fetch("/api/upload", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    throw new Error(errorPayload?.detail || response.statusText);
  }

  const result = await response.json();
  showToast(`${result.message} (${result.uploaded_chunks} resumes indexed)`);

  const baseCandidate = {
    candidate_id: null,
    name: (els.candidateName.value || "Anonymous Candidate").trim(),
    headline: "",
    target_role: (els.candidateTargetRole.value || "").trim(),
    years_experience: clampNumber(els.candidateYears.value, 0),
    location: (els.candidateLocation.value || "Remote").trim(),
    skills: splitList(els.candidateSkills.value || ""),
    resume_text: fileTexts.join("\n\n").trim(),
    source: `${els.uploadSourcePrefix.value || "candidates"}/upload`,
    stage: els.candidateStage.value || "screening",
  };

  if (result.candidate_ids?.length) {
    result.candidate_ids.forEach((id, index) => {
      const snapshot = {
        ...baseCandidate,
        candidate_id: id,
        resume_text: (fileTexts[index] || baseCandidate.resume_text || "").trim(),
        source: `${els.uploadSourcePrefix.value || "candidates"}/${Array.from(files)[index]?.name || "upload"}`,
      };
      state.candidates = upsertById(state.candidates, snapshot, "candidate_id");
    });
    saveToStorage(STORAGE_KEYS.candidates, state.candidates);
  }

  await refreshStatus();
  await refreshEntities();
  if (result.candidate_ids?.length) {
    selectCandidate(result.candidate_ids[0]);
  }
}

function jobSnapshotFromForm() {
  return {
    job_id: null,
    title: els.jobTitle.value.trim() || "Untitled Role",
    description: els.jobDescription.value.trim() || "Role description not provided.",
    department: els.jobDepartment.value.trim() || "engineering",
    location: els.jobLocation.value.trim() || "Remote",
    min_years_experience: clampNumber(els.jobMinYears.value, 0),
    must_have_skills: splitList(els.jobMustHave.value),
    nice_to_have_skills: splitList(els.jobNiceHave.value),
    interview_focus: splitList(els.jobFocus.value),
  };
}

async function createJob() {
  const job = jobSnapshotFromForm();
  job.job_id = job.job_id || `job_${Math.random().toString(16).slice(2)}`;

  state.jobs = upsertById(state.jobs, job, "job_id");
  saveToStorage(STORAGE_KEYS.jobs, state.jobs);

  await refreshEntities();
  selectJob(job.job_id);
  showToast(`Saved job role: ${job.title}`);
}

async function rankCandidates() {
  const payload = {
    job: jobSnapshotFromForm(),
    query: els.searchQuery.value.trim() || els.jobTitle.value.trim(),
    role: els.searchRole.value,
    location: els.searchLocation.value,
    stage: els.searchStage.value,
    top_k: topKValue("search"),
  };
  const response = await postJson("/api/rank", payload);

  if (response.job) {
    state.jobs = upsertById(state.jobs, response.job, "job_id");
    saveToStorage(STORAGE_KEYS.jobs, state.jobs);
  }

  state.candidates = (response.ranked_candidates || []).reduce((acc, item) => {
    return upsertById(acc, candidateSnapshotFromResult(item), "candidate_id");
  }, state.candidates);
  saveToStorage(STORAGE_KEYS.candidates, state.candidates);
  refreshEntities();

  renderCandidateCards(response.ranked_candidates, els.rankResults, { kind: "rank" });
  showToast(`Ranked ${response.ranked_candidates.length} candidates for ${response.job.title}.`);
  if (response.ranked_candidates?.length) {
    selectCandidate(response.ranked_candidates[0].id);
  }
}

async function requestInterviewPlan() {
  const candidate = candidateSnapshotFromState(getSelectedCandidate());
  const job = jobSnapshotFromState(getSelectedJob()) || jobSnapshotFromForm();
  if (!candidate || !job) {
    showToast("Choose a candidate and job first.", "error");
    return;
  }

  const payload = await postJson("/api/interview/plan", {
    candidate,
    job,
    num_questions: Number(els.interviewCount.value),
  });
  if (payload.candidate) {
    state.candidates = upsertById(state.candidates, payload.candidate, "candidate_id");
    saveToStorage(STORAGE_KEYS.candidates, state.candidates);
  }
  if (payload.job) {
    state.jobs = upsertById(state.jobs, payload.job, "job_id");
    saveToStorage(STORAGE_KEYS.jobs, state.jobs);
  }
  refreshEntities();
  renderInterviewQuestions(payload);
  showToast("Adaptive interview questions generated.");
}

function readInterviewAnswers() {
  return state.currentQuestions.map((question, index) => {
    const answerField = document.getElementById(`answer-${index}`);
    return {
      prompt: question.question,
      answer: (answerField?.value || "").trim(),
    };
  });
}

async function evaluateInterview() {
  if (!state.currentQuestions.length) {
    showToast("Generate interview questions first.", "error");
    return;
  }
  const candidate = candidateSnapshotFromState(getSelectedCandidate());
  const job = jobSnapshotFromState(getSelectedJob()) || jobSnapshotFromForm();
  const payload = await postJson("/api/interview/evaluate", {
    candidate,
    job,
    answers: readInterviewAnswers(),
    telemetry: {
      ...state.telemetry,
      multiple_faces_detected: els.multipleFaces.checked,
    },
  });
  renderInterviewResult(payload);
  showToast(`Interview evaluated. Overall score ${Number(payload.overall_score || 0).toFixed(1)}.`);
}

async function requestResumeFeedback(candidateOverride = null, jobOverride = null) {
  const candidate = candidateOverride || candidateSnapshotFromState(getSelectedCandidate());
  const job = jobOverride || jobSnapshotFromState(getSelectedJob()) || jobSnapshotFromForm();
  if (!candidate || !job) {
    showToast("Choose a candidate and job first.", "error");
    return;
  }
  const payload = await postJson("/api/resume/feedback", {
    candidate,
    job,
  });
  renderFeedback(payload);
  showToast(`Loaded feedback for ${payload.candidate?.name || "candidate"}.`);
}

async function requestFraudScore() {
  const payload = await postJson("/api/fraud/score", {
    telemetry: {
      ...state.telemetry,
      multiple_faces_detected: els.multipleFaces.checked,
    },
  });
  renderFraudResult(payload);
  showToast(`Fraud check complete: ${payload.label}.`);
}

function loadSamplePrompt() {
  const prompt = state.examples[0] || "Rank these resumes for a senior AI engineer role.";
  els.searchQuery.value = prompt;
  els.answerQuestion.value = prompt;
  els.jobTitle.value = "Senior AI Engineer";
  els.searchQuery.focus();
  showToast("Loaded sample prompt and job title.");
}

function markActivity() {
  if (!state.interviewActive) {
    return;
  }
  state.lastActivityAt = Date.now();
}

function attachTelemetryListeners() {
  document.addEventListener("visibilitychange", () => {
    if (!state.interviewActive) {
      return;
    }
    if (document.hidden) {
      state.telemetry.tab_switches += 1;
      renderTelemetryPanel();
    }
  });

  window.addEventListener("blur", () => {
    if (!state.interviewActive) {
      return;
    }
    state.telemetry.blur_events += 1;
    renderTelemetryPanel();
  });

  document.addEventListener("copy", () => {
    if (!state.interviewActive) {
      return;
    }
    state.telemetry.copy_events += 1;
    renderTelemetryPanel();
  });

  document.addEventListener("paste", () => {
    if (!state.interviewActive) {
      return;
    }
    state.telemetry.paste_events += 1;
    renderTelemetryPanel();
  });

  document.addEventListener("keydown", markActivity);
  document.addEventListener("mousemove", markActivity, { passive: true });
  document.addEventListener("pointerdown", markActivity, { passive: true });

  setInterval(() => {
    if (!state.interviewActive) {
      return;
    }
    state.telemetry.idle_seconds = Math.max(0, (Date.now() - state.lastActivityAt) / 1000);
    renderTelemetryPanel();
  }, 1000);
}

async function initialize() {
  setStatus(bootstrap);
  populateFilterSelects(state.filters);
  renderPromptChips(state.examples);
  wireRangeCounter("search-top-k", "search-top-k-value");
  wireRangeCounter("answer-top-k", "answer-top-k-value");
  wireRangeCounter("interview-count", "interview-count-value");
  renderTelemetryPanel();

  if (state.examples.length) {
    els.searchQuery.value = state.examples[0];
    els.answerQuestion.value = state.examples[0];
  }

  await refreshEntities().catch((error) => {
    showToast(error.message, "error");
  });

  if (!state.candidates.length || !state.jobs.length) {
    await refreshStatus().catch((error) => {
      showToast(error.message, "error");
    });
  }

  if (state.candidates.length && state.jobs.length) {
    selectCandidate(state.candidates[0].candidate_id || state.candidates[0].id, { silent: true });
    selectJob(state.jobs[0].job_id || state.jobs[0].id, { silent: true });
  }

  resetSearchResults();
  resetInterviewSession();
}

document.addEventListener("DOMContentLoaded", () => {
  initialize();
  attachTelemetryListeners();

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
      await uploadResume(event);
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.jobForm.addEventListener("submit", (event) => {
    event.preventDefault();
  });

  els.createJobButton.addEventListener("click", async () => {
    try {
      await createJob();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.rankButton.addEventListener("click", async () => {
    try {
      await rankCandidates();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.generateInterviewButton.addEventListener("click", async () => {
    try {
      await requestInterviewPlan();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.evaluateInterviewButton.addEventListener("click", async () => {
    try {
      await evaluateInterview();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.resumeFeedbackButton.addEventListener("click", async () => {
    try {
      await requestResumeFeedback();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.fraudCheckButton.addEventListener("click", async () => {
    try {
      await requestFraudScore();
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.resetInterviewButton.addEventListener("click", () => {
    resetInterviewSession();
    showToast("Interview session reset.");
  });

  els.resetSessionButton.addEventListener("click", () => {
    resetInterviewSession();
    showToast("Interview session reset.");
  });

  els.samplePromptButton.addEventListener("click", loadSamplePrompt);

  els.refreshButton.addEventListener("click", async () => {
    try {
      await refreshStatus();
      await refreshEntities();
      showToast("Status refreshed.");
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  els.clearSearchButton.addEventListener("click", () => {
    els.searchQuery.value = "";
    resetSearchResults();
    showToast("Search cleared.");
  });

  els.useSearchQueryButton.addEventListener("click", () => {
    els.answerQuestion.value = els.searchQuery.value || els.answerQuestion.value;
    showToast("Copied the search query into the explainability panel.");
  });

  els.interviewCandidate.addEventListener("change", () => {
    state.selectedCandidateId = els.interviewCandidate.value;
  });

  els.interviewJob.addEventListener("change", () => {
    state.selectedJobId = els.interviewJob.value;
  });

  els.multipleFaces.addEventListener("change", () => {
    state.telemetry.multiple_faces_detected = els.multipleFaces.checked;
    renderTelemetryPanel();
  });

  els.searchQuery.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      els.searchForm.requestSubmit();
    }
  });
});
