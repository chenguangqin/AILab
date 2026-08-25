const state = {
  config: null,
  manifest: null,
  evaluationTimer: null,
};

const byId = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return payload;
}

function toast(message, error = false) {
  const element = byId("toast");
  element.textContent = message;
  element.classList.toggle("error", error);
  element.classList.add("visible");
  window.setTimeout(() => element.classList.remove("visible"), 2800);
}

function setBusy(button, busy, busyText, normalText) {
  button.disabled = busy;
  button.textContent = busy ? busyText : normalText;
}

function hydrateSettings(config) {
  state.config = config;
  const query = config.query;
  const index = config.index;
  byId("query-rewrite").checked = query.query_rewrite;
  byId("active-only").checked = query.active_only;
  byId("retrieval-top-k").value = query.retrieval_top_k;
  byId("rerank-candidate-k").value = query.rerank_candidate_k;
  byId("rerank-top-n").value = query.rerank_top_n;
  byId("hybrid-alpha").value = query.hybrid_alpha;
  byId("alpha-value").textContent = Number(query.hybrid_alpha).toFixed(2);
  byId("chunk-strategy").value = index.chunk_strategy;
  byId("chunk-size").value = index.chunk_size;
  byId("chunk-overlap").value = index.chunk_overlap;
  byId("embedding-provider").value = index.embedding_provider;
  byId("index-version").textContent = `index: ${index.index_version}`;
}

function queryConfig() {
  return {
    intent_routing: state.config.query.intent_routing,
    query_rewrite: byId("query-rewrite").checked,
    retrieval_top_k: Number(byId("retrieval-top-k").value),
    hybrid_alpha: Number(byId("hybrid-alpha").value),
    rerank_candidate_k: Number(byId("rerank-candidate-k").value),
    rerank_top_n: Number(byId("rerank-top-n").value),
    min_relevance_score: state.config.query.min_relevance_score,
    max_context_chars: state.config.query.max_context_chars,
    active_only: byId("active-only").checked,
  };
}

function indexConfig() {
  return {
    chunk_strategy: byId("chunk-strategy").value,
    chunk_size: Number(byId("chunk-size").value),
    chunk_overlap: Number(byId("chunk-overlap").value),
    embedding_provider: byId("embedding-provider").value,
    vector_backend: state.config.index.vector_backend,
    index_version: state.config.index.index_version,
  };
}

async function loadStatus() {
  const payload = await api("/api/status");
  state.manifest = payload.manifest;
  hydrateSettings(payload.config);
  byId("runtime-summary").textContent =
    `${payload.manifest.document_count} documents · ${payload.manifest.chunk_count} chunks · ${payload.graph.workflow_version}`;
  const langfuse = byId("langfuse-status");
  langfuse.textContent = payload.langfuse_enabled ? "Langfuse 已连接" : "本地 Trace";
  langfuse.className = `status-badge ${payload.langfuse_enabled ? "active" : "neutral"}`;
}

function renderTrajectory(trajectory) {
  document.querySelectorAll(".pipeline span").forEach((node) => {
    node.classList.toggle("complete", trajectory.includes(node.dataset.node));
  });
}

function renderCitations(citations) {
  byId("citation-count").textContent = citations.length;
  const body = byId("citation-body");
  body.replaceChildren();
  if (!citations.length) {
    const row = body.insertRow();
    const cell = row.insertCell();
    cell.colSpan = 4;
    cell.className = "empty-cell";
    cell.textContent = "暂无引用";
    return;
  }
  citations.forEach((citation) => {
    const row = body.insertRow();
    [
      citation.evidence_id,
      citation.document_id,
      citation.page ?? "--",
      citation.region ?? citation.table_cell ?? "--",
    ].forEach((value) => {
      row.insertCell().textContent = value;
    });
  });
}

byId("query-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = byId("query-submit");
  setBusy(button, true, "运行中", "运行查询");
  renderTrajectory([]);
  try {
    const result = await api("/api/query", {
      method: "POST",
      body: JSON.stringify({ question: byId("question").value.trim() }),
    });
    byId("answer").textContent = result.answer;
    byId("answer").classList.remove("empty");
    byId("query-meta").textContent =
      `${result.latency_ms.toFixed(1)} ms · trace ${result.metadata.trace_id.slice(0, 8)}`;
    renderTrajectory(result.metadata.trajectory || []);
    renderCitations(result.citations);
  } catch (error) {
    toast(error.message, true);
  } finally {
    setBusy(button, false, "运行中", "运行查询");
  }
});

byId("hybrid-alpha").addEventListener("input", (event) => {
  byId("alpha-value").textContent = Number(event.target.value).toFixed(2);
});

byId("query-settings").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.submitter;
  setBusy(button, true, "应用中", "应用查询设置");
  try {
    const payload = await api("/api/config/query", {
      method: "PUT",
      body: JSON.stringify({ query: queryConfig() }),
    });
    hydrateSettings(payload.config);
    byId("settings-state").textContent = "查询设置已应用";
    toast("查询设置已应用，无需重建索引");
  } catch (error) {
    toast(error.message, true);
  } finally {
    setBusy(button, false, "应用中", "应用查询设置");
  }
});

byId("index-settings").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = byId("rebuild-index");
  setBusy(button, true, "构建中", "重建索引");
  byId("settings-state").textContent = "正在构建索引";
  try {
    const payload = await api("/api/index/rebuild", {
      method: "POST",
      body: JSON.stringify({ index: indexConfig() }),
    });
    state.manifest = payload.manifest;
    hydrateSettings(payload.config);
    byId("runtime-summary").textContent =
      `${payload.manifest.document_count} documents · ${payload.manifest.chunk_count} chunks · rag-langgraph-v1`;
    byId("settings-state").textContent = "索引已更新";
    toast(`索引已更新：${payload.manifest.chunk_count} chunks`);
  } catch (error) {
    byId("settings-state").textContent = "索引构建失败";
    toast(error.message, true);
  } finally {
    setBusy(button, false, "构建中", "重建索引");
  }
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
    tab.classList.add("active");
    byId(tab.dataset.tab).classList.add("active");
  });
});

const metricKeys = [
  ["mean_evidence_recall", "Evidence Recall"],
  ["mean_mrr", "MRR"],
  ["mean_ndcg", "nDCG"],
  ["mean_citation_recall", "Citation Recall"],
  ["mean_abstention_accuracy", "Abstention"],
  ["mean_input_chars", "Context Chars"],
];

function renderMetrics(summary) {
  const grid = byId("metric-grid");
  grid.replaceChildren();
  metricKeys.forEach(([key, label]) => {
    const item = document.createElement("div");
    const name = document.createElement("span");
    const value = document.createElement("strong");
    name.textContent = label;
    const number = summary[key];
    value.textContent = key === "mean_input_chars"
      ? Number(number).toFixed(0)
      : Number(number).toFixed(3);
    item.append(name, value);
    grid.append(item);
  });
}

async function pollEvaluation(jobId) {
  try {
    const job = await api(`/api/evaluations/${jobId}`);
    byId("evaluation-status").textContent = `${job.status} · ${job.job_id.slice(0, 8)}`;
    if (job.status === "completed") {
      window.clearInterval(state.evaluationTimer);
      state.evaluationTimer = null;
      renderMetrics(job.summary);
      byId("evaluation-index").textContent = `${job.case_count} cases · ${job.index_version}`;
      setBusy(byId("run-evaluation"), false, "评估中", "启动评估");
      toast("离线评估完成");
      return true;
    } else if (job.status === "failed") {
      window.clearInterval(state.evaluationTimer);
      state.evaluationTimer = null;
      setBusy(byId("run-evaluation"), false, "评估中", "启动评估");
      toast(job.error, true);
      return true;
    }
    return false;
  } catch (error) {
    window.clearInterval(state.evaluationTimer);
    state.evaluationTimer = null;
    setBusy(byId("run-evaluation"), false, "评估中", "启动评估");
    toast(error.message, true);
    return true;
  }
}

byId("run-evaluation").addEventListener("click", async () => {
  const button = byId("run-evaluation");
  setBusy(button, true, "评估中", "启动评估");
  try {
    const job = await api("/api/evaluations", {
      method: "POST",
      body: JSON.stringify({ split: byId("eval-split").value }),
    });
    byId("evaluation-status").textContent = `queued · ${job.job_id.slice(0, 8)}`;
    const completed = await pollEvaluation(job.job_id);
    if (!completed && !state.evaluationTimer) {
      state.evaluationTimer = window.setInterval(
        () => pollEvaluation(job.job_id),
        600,
      );
    }
  } catch (error) {
    setBusy(button, false, "评估中", "启动评估");
    toast(error.message, true);
  }
});

loadStatus().catch((error) => toast(error.message, true));
