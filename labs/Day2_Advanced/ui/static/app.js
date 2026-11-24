(() => {
  const els = {
    title: document.getElementById("app-title"),
    subtitle: document.getElementById("app-subtitle"),
    eyebrow: document.getElementById("lab-eyebrow"),
    model: document.getElementById("model-label"),
    selectedLab: document.getElementById("selected-lab-label"),
    labSelect: document.getElementById("lab-select"),
    labDescription: document.getElementById("lab-description"),
    queryLabel: document.getElementById("query-label"),
    query: document.getElementById("query-input"),
    hitl: document.getElementById("hitl-toggle"),
    hitlWrap: document.getElementById("hitl-wrap"),
    runBtn: document.getElementById("run-btn"),
    examples: document.getElementById("examples"),
    pipeline: document.getElementById("pipeline"),
    timeline: document.getElementById("timeline"),
    status: document.getElementById("run-status"),
    hitlPanel: document.getElementById("hitl-panel"),
    hitlDetails: document.getElementById("hitl-details"),
    hitlGuidance: document.getElementById("hitl-guidance"),
    hitlSend: document.getElementById("hitl-send"),
    finalOutput: document.getElementById("final-output"),
    runReport: document.getElementById("run-report"),
    taskList: document.getElementById("task-list"),
    compliance: document.getElementById("compliance-badge"),
  };

  const state = {
    threadId: null,
    labId: null,
    labs: [],
    flow: [],
    busy: false,
  };

  function currentLab() {
    return state.labs.find((lab) => lab.id === state.labId) || state.labs[0];
  }

  function setStatus(kind, label) {
    els.status.className = `status ${kind}`;
    els.status.textContent = label;
  }

  function addEvent(node, message) {
    const row = document.createElement("div");
    row.className = "event";
    row.innerHTML = `<div class="node">${escapeHtml(node)}</div><div class="msg">${escapeHtml(
      message || ""
    )}</div>`;
    els.timeline.prepend(row);
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function renderPipeline(activeNode) {
    els.pipeline.querySelectorAll("li").forEach((li) => {
      const name = li.dataset.node;
      if (name === activeNode) {
        li.classList.add("active");
        li.classList.remove("done");
      } else if (li.classList.contains("active")) {
        li.classList.remove("active");
        li.classList.add("done");
      }
    });
  }

  function buildPipeline(flow) {
    els.pipeline.innerHTML = "";
    (flow || []).forEach((node) => {
      const li = document.createElement("li");
      li.dataset.node = node;
      li.textContent = node;
      els.pipeline.appendChild(li);
    });
  }

  function renderExamples(examples) {
    els.examples.innerHTML = "";
    (examples || []).forEach((prompt) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = prompt;
      btn.addEventListener("click", () => {
        els.query.value = prompt;
        els.query.focus();
      });
      els.examples.appendChild(btn);
    });
  }

  function applyLab(labId) {
    state.labId = labId;
    const lab = currentLab();
    if (!lab) return;
    state.flow = lab.flow || [];
    els.selectedLab.textContent = lab.name;
    els.labDescription.textContent = lab.description || "";
    els.queryLabel.textContent = lab.input_label || "Query";
    els.runBtn.textContent = lab.run_label || "Run lab";
    els.eyebrow.textContent = lab.name;
    els.hitlWrap.style.display = lab.supports_hitl ? "inline-flex" : "none";
    if (!lab.supports_hitl) els.hitl.checked = false;
    buildPipeline(state.flow);
    renderExamples(lab.examples || []);
    if (!els.query.value.trim() && lab.examples?.length) {
      els.query.value = lab.examples[0];
    }
  }

  function renderTasks(tasks) {
    els.taskList.innerHTML = "";
    (tasks || []).forEach((task) => {
      const div = document.createElement("div");
      div.className = "task";
      const role = task.assigned_to || task.intent || "item";
      const status = task.status || task.urgency || "info";
      div.innerHTML = `<strong>${escapeHtml(role)} · ${escapeHtml(
        status
      )}</strong><span>${escapeHtml(task.description || task.summary || "")}</span>`;
      els.taskList.appendChild(div);
    });
  }

  function showHitl(payload) {
    els.hitlPanel.classList.remove("hidden");
    const lines = [];
    if (payload.task) lines.push(`Task: ${payload.task}`);
    if (payload.score != null) lines.push(`Score: ${payload.score}`);
    if (payload.classification) {
      lines.push(
        `Classification: ${payload.classification.intent || ""} / ${
          payload.classification.urgency || ""
        }`
      );
    }
    if (payload.draft_response) lines.push(`\nDraft:\n${payload.draft_response}`);
    if (payload.policy_violations?.length) {
      lines.push("Policy violations:");
      payload.policy_violations.forEach((item) => lines.push(`- ${item}`));
    }
    if (payload.feedback) lines.push(`\n${payload.feedback}`);
    if (payload.prompt) lines.push(`\n${payload.prompt}`);
    els.hitlDetails.textContent = lines.join("\n") || JSON.stringify(payload, null, 2);
    setStatus("waiting", "Awaiting review");
  }

  function hideHitl() {
    els.hitlPanel.classList.add("hidden");
    els.hitlGuidance.value = "";
  }

  async function consumeSse(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";

      for (const chunk of chunks) {
        const lines = chunk.split("\n");
        let event = "message";
        let data = "";
        for (const line of lines) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (!data) continue;
        handleEvent(event, JSON.parse(data));
      }
    }
  }

  function handleEvent(event, data) {
    switch (event) {
      case "run_started":
      case "resume_started":
        state.threadId = data.thread_id;
        if (data.lab_id) state.labId = data.lab_id;
        if (data.flow?.length) {
          state.flow = data.flow;
          buildPipeline(state.flow);
        }
        setStatus("running", "Running");
        addEvent(
          "system",
          event === "run_started"
            ? `Started ${data.lab_name || data.lab_id || "lab"}`
            : `Resumed: ${data.decision}`
        );
        break;
      case "node":
        renderPipeline(data.node);
        addEvent(
          data.node,
          data.payload?.message || data.payload?.latest_action?.action || "updated"
        );
        if (data.payload?.tasks) renderTasks(data.payload.tasks);
        break;
      case "interrupt":
        showHitl(data.payload || {});
        state.busy = false;
        els.runBtn.disabled = false;
        break;
      case "final":
        hideHitl();
        els.finalOutput.textContent = data.result?.final_output || "(empty)";
        els.runReport.textContent = data.report || "No report";
        if (data.result?.classification) {
          renderTasks([
            {
              assigned_to: data.result.classification.intent,
              status: data.result.classification.urgency,
              description: data.result.classification.summary,
            },
          ]);
        } else {
          renderTasks(data.result?.tasks || []);
        }
        const verdict = data.result?.compliance?.verdict || "—";
        els.compliance.textContent = verdict;
        els.compliance.className = `badge ${verdict}`;
        state.flow.forEach((node) => {
          const li = els.pipeline.querySelector(`li[data-node="${node}"]`);
          if (li) {
            li.classList.remove("active");
            li.classList.add("done");
          }
        });
        setStatus("done", "Complete");
        break;
      case "done":
        state.busy = false;
        els.runBtn.disabled = false;
        break;
      case "error":
        setStatus("error", "Error");
        addEvent("error", data.message || "Unknown error");
        els.finalOutput.textContent = data.message || "Run failed";
        state.busy = false;
        els.runBtn.disabled = false;
        break;
      default:
        break;
    }
  }

  async function startRun() {
    const query = els.query.value.trim();
    if (!query || state.busy) return;

    state.busy = true;
    els.runBtn.disabled = true;
    hideHitl();
    els.timeline.innerHTML = "";
    els.taskList.innerHTML = "";
    els.finalOutput.textContent = "Running selected lab…";
    els.runReport.textContent = "Collecting metrics…";
    els.compliance.textContent = "—";
    els.compliance.className = "badge";
    buildPipeline(state.flow);
    setStatus("running", "Running");

    try {
      const response = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          lab_id: state.labId,
          enable_hitl: els.hitl.checked,
        }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      await consumeSse(response);
    } catch (err) {
      handleEvent("error", { message: String(err) });
    } finally {
      if (els.hitlPanel.classList.contains("hidden")) {
        state.busy = false;
        els.runBtn.disabled = false;
      }
    }
  }

  async function resume(decision) {
    if (!state.threadId || !decision.trim()) return;
    state.busy = true;
    els.runBtn.disabled = true;
    hideHitl();
    setStatus("running", "Resuming");

    try {
      const response = await fetch("/api/runs/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: state.threadId,
          lab_id: state.labId,
          decision: decision.trim(),
        }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      await consumeSse(response);
    } catch (err) {
      handleEvent("error", { message: String(err) });
    } finally {
      if (els.hitlPanel.classList.contains("hidden")) {
        state.busy = false;
        els.runBtn.disabled = false;
      }
    }
  }

  async function bootstrap() {
    const response = await fetch("/api/bootstrap");
    const data = await response.json();
    els.title.textContent = data.title || "Agent Desk";
    els.subtitle.textContent = data.subtitle || "";
    els.model.textContent = data.model || "unknown";
    state.labs = data.labs || [];
    els.labSelect.innerHTML = "";
    state.labs.forEach((lab) => {
      const option = document.createElement("option");
      option.value = lab.id;
      option.textContent = lab.name;
      els.labSelect.appendChild(option);
    });
    const initial = data.default_lab_id || state.labs[0]?.id;
    els.labSelect.value = initial;
    applyLab(initial);
  }

  els.labSelect.addEventListener("change", () => {
    applyLab(els.labSelect.value);
  });
  els.runBtn.addEventListener("click", startRun);
  els.query.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      startRun();
    }
  });
  els.hitlPanel.querySelectorAll("button[data-decision]").forEach((btn) => {
    btn.addEventListener("click", () => resume(btn.dataset.decision));
  });
  els.hitlSend.addEventListener("click", () => resume(els.hitlGuidance.value));
  els.hitlGuidance.addEventListener("keydown", (event) => {
    if (event.key === "Enter") resume(els.hitlGuidance.value);
  });

  bootstrap().catch((err) => {
    els.model.textContent = "unavailable";
    addEvent("error", `Bootstrap failed: ${err}`);
  });
})();
