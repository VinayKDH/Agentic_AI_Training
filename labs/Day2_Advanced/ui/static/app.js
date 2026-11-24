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
    autonomySelect: document.getElementById("autonomy-select"),
    autonomySummary: document.getElementById("autonomy-summary"),
    autonomyLabel: document.getElementById("autonomy-label"),
    autonomyPill: document.getElementById("autonomy-pill"),
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
    currentAgentName: document.getElementById("current-agent-name"),
    currentAgentState: document.getElementById("current-agent-state"),
    currentAgentSummary: document.getElementById("current-agent-summary"),
    handoffBanner: document.getElementById("handoff-banner"),
    handoffFrom: document.getElementById("handoff-from"),
    handoffTo: document.getElementById("handoff-to"),
    handoffReason: document.getElementById("handoff-reason"),
    stepRail: document.getElementById("step-rail"),
    stepCount: document.getElementById("step-count"),
  };

  const state = {
    threadId: null,
    labId: null,
    labs: [],
    flow: [],
    busy: false,
    autonomyLevels: [],
    autonomyLevel: "L2",
    steps: [],
    selectedStepId: null,
    lastAgent: null,
  };

  function currentLab() {
    return state.labs.find((lab) => lab.id === state.labId) || state.labs[0];
  }

  function setStatus(kind, label) {
    els.status.className = `status ${kind}`;
    els.status.textContent = label;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function formatTime(date = new Date()) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function setCurrentAgent(name, status, summary) {
    els.currentAgentName.textContent = name || "Idle";
    els.currentAgentState.textContent = status || "waiting";
    els.currentAgentState.className = `agent-state-chip ${status || "waiting"}`;
    els.currentAgentSummary.textContent =
      summary || "Start a run to watch step-by-step handoffs.";
  }

  function showHandoff(from, to, reason) {
    els.handoffBanner.classList.remove("hidden");
    els.handoffFrom.textContent = from || "—";
    els.handoffTo.textContent = to || "—";
    els.handoffReason.textContent = reason || "";
  }

  function hideHandoff() {
    els.handoffBanner.classList.add("hidden");
  }

  function resetSteps() {
    state.steps = [];
    state.selectedStepId = null;
    state.lastAgent = null;
    renderStepRail();
    hideHandoff();
    setCurrentAgent("Idle", "waiting", "Start a run to watch step-by-step handoffs.");
  }

  function upsertStep(step) {
    const existing = state.steps.find((item) => item.id === step.id);
    if (existing) {
      Object.assign(existing, step);
    } else {
      state.steps.push(step);
    }
    state.selectedStepId = step.id;
    renderStepRail();
  }

  function markPreviousDone(exceptId) {
    state.steps.forEach((step) => {
      if (step.id !== exceptId && step.status === "active" && step.kind === "agent") {
        step.status = "done";
      }
    });
  }

  function renderStepRail() {
    els.stepRail.innerHTML = "";
    els.stepCount.textContent = `${state.steps.length} step${
      state.steps.length === 1 ? "" : "s"
    }`;

    state.steps.forEach((step) => {
      const li = document.createElement("li");
      li.className = `step-item ${step.status}${
        state.selectedStepId === step.id ? " selected" : ""
      }${step.kind === "handoff" ? " handoff-only" : ""}`;
      li.dataset.stepId = step.id;

      const details = step.details || step.summary || "";
      li.innerHTML = `
        <div class="step-marker"><span class="step-dot"></span></div>
        <div class="step-card">
          <div class="step-card-top">
            <span class="step-agent">${escapeHtml(step.title)}</span>
            <span class="step-meta">${escapeHtml(step.status)} · ${escapeHtml(
        step.time || ""
      )}</span>
          </div>
          <p class="step-summary">${escapeHtml(step.summary || "")}</p>
          ${
            step.handoff
              ? `<div class="step-handoff">${escapeHtml(step.handoff)}</div>`
              : ""
          }
          <div class="step-details">${escapeHtml(details)}</div>
        </div>
      `;
      li.addEventListener("click", () => {
        state.selectedStepId = step.id;
        renderStepRail();
        if (step.kind === "agent") {
          setCurrentAgent(step.agent, step.status, step.summary);
        }
      });
      els.stepRail.appendChild(li);
    });

    const active = [...els.stepRail.querySelectorAll(".step-item")].pop();
    if (active) active.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function addEvent(node, message) {
    if (!els.timeline) return;
    const row = document.createElement("div");
    row.className = "event";
    row.innerHTML = `<div class="node">${escapeHtml(node)}</div><div class="msg">${escapeHtml(
      message || ""
    )}</div>`;
    els.timeline.prepend(row);
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
    const showAutonomy = lab.id === "day2_advanced";
    els.autonomySelect.style.display = showAutonomy ? "block" : "none";
    els.autonomyLabel.style.display = showAutonomy ? "block" : "none";
    els.autonomySummary.style.display = showAutonomy ? "block" : "none";
    if (showAutonomy) applyAutonomy(els.autonomySelect.value || state.autonomyLevel);
    buildPipeline(state.flow);
    renderExamples(lab.examples || []);
    if (!els.query.value.trim() && lab.examples?.length) {
      els.query.value = lab.examples[0];
    }
  }

  function applyAutonomy(levelId) {
    state.autonomyLevel = levelId || "L2";
    const level =
      state.autonomyLevels.find((item) => item.id === state.autonomyLevel) ||
      state.autonomyLevels[0];
    els.autonomyPill.textContent = state.autonomyLevel;
    els.autonomySummary.textContent = level
      ? `${level.name}: ${level.summary}`
      : "Conditional autonomy with policy escalation.";
    if (state.autonomyLevel === "L4") {
      els.hitl.checked = false;
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
    if (payload.type) lines.push(`Gate: ${payload.type}`);
    if (payload.autonomy_level) lines.push(`Autonomy: ${payload.autonomy_level}`);
    if (payload.governance?.escalation_triggers?.length) {
      lines.push("Escalation triggers:");
      payload.governance.escalation_triggers.forEach((item) => lines.push(`- ${item}`));
    }
    if (payload.task) lines.push(`Task: ${payload.task}`);
    if (payload.score != null) lines.push(`Score: ${payload.score}`);
    if (payload.plan?.tasks?.length) {
      lines.push("Plan tasks:");
      payload.plan.tasks.forEach((task) =>
        lines.push(`- [${task.assigned_to}/${task.risk_level}] ${task.description}`)
      );
    }
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
    setStatus("waiting", "Governance gate");
    setCurrentAgent("human", "blocked", payload.prompt || "Waiting for human decision");
  }

  function hideHitl() {
    els.hitlPanel.classList.add("hidden");
    els.hitlGuidance.value = "";
  }

  function detailText(payload = {}) {
    const lines = [];
    if (payload.state_summary) lines.push(payload.state_summary);
    if (payload.message) lines.push(payload.message);
    if (payload.review) {
      lines.push(
        `Review: ${payload.review.decision || "n/a"} · score ${payload.review.score ?? "n/a"}`
      );
      if (payload.review.feedback) lines.push(payload.review.feedback);
    }
    if (payload.artifact) {
      lines.push(`Artifact: ${payload.artifact.type || "output"}`);
      if (payload.artifact.language) lines.push(`Language: ${payload.artifact.language}`);
      if (payload.artifact.excerpt) lines.push(payload.artifact.excerpt);
    }
    if (payload.autonomy_level) lines.push(`Autonomy: ${payload.autonomy_level}`);
    return lines.join("\n\n") || "No detail yet.";
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
        setCurrentAgent(
          event === "run_started" ? "orchestrator" : "resuming",
          "active",
          event === "run_started"
            ? `Started ${data.lab_name || data.lab_id || "lab"} · autonomy ${
                data.autonomy_level || state.autonomyLevel
              }`
            : `Resumed with decision: ${data.decision}`
        );
        upsertStep({
          id: `${event}-${Date.now()}`,
          kind: "agent",
          agent: event === "run_started" ? "orchestrator" : "resume",
          title: event === "run_started" ? "Run started" : "Run resumed",
          status: "done",
          time: formatTime(),
          summary:
            event === "run_started"
              ? `Lab ${data.lab_name || data.lab_id || "selected"} ready`
              : `Human decision: ${data.decision}`,
          details: JSON.stringify(data, null, 2),
        });
        addEvent(
          "system",
          event === "run_started"
            ? `Started ${data.lab_name || data.lab_id || "lab"}`
            : `Resumed: ${data.decision}`
        );
        break;

      case "handoff":
        showHandoff(data.from, data.to, data.reason);
        upsertStep({
          id: `handoff-${data.step || Date.now()}`,
          kind: "handoff",
          agent: "handoff",
          title: `Handoff`,
          status: "done",
          time: formatTime(),
          summary: data.reason || `${data.from} → ${data.to}`,
          handoff: `${data.from} → ${data.to}`,
          details: data.state_summary || data.reason || "",
        });
        setCurrentAgent(
          data.to,
          data.to === "human" ? "blocked" : "active",
          data.reason || `Handed off from ${data.from}`
        );
        addEvent("handoff", `${data.from} → ${data.to}: ${data.reason || ""}`);
        break;

      case "node": {
        const payload = data.payload || {};
        const agent = data.node;
        markPreviousDone(`node-${data.step}`);
        renderPipeline(agent);
        setCurrentAgent(
          agent,
          "active",
          payload.state_summary || payload.message || `${agent} working…`
        );
        upsertStep({
          id: `node-${data.step || agent}-${Date.now()}`,
          kind: "agent",
          agent,
          title: `Step ${data.step || "·"} · ${agent}`,
          status: "active",
          time: formatTime(),
          summary: payload.state_summary || payload.message || `${agent} updated`,
          handoff: data.from_node ? `${data.from_node} → ${agent}` : "",
          details: detailText(payload),
        });
        // Mark this new step active; previous agent steps done
        state.steps.forEach((step) => {
          if (step.kind === "agent" && step.agent !== agent && step.status === "active") {
            step.status = "done";
          }
        });
        renderStepRail();
        if (payload.tasks) renderTasks(payload.tasks);
        addEvent(
          agent,
          payload.message || payload.latest_action?.action || payload.state_summary || "updated"
        );
        state.lastAgent = agent;
        break;
      }

      case "interrupt":
        showHitl(data.payload || {});
        markPreviousDone(null);
        upsertStep({
          id: `interrupt-${Date.now()}`,
          kind: "agent",
          agent: "human",
          title: "Human gate",
          status: "blocked",
          time: formatTime(),
          summary: (data.payload && data.payload.prompt) || "Awaiting human decision",
          handoff: data.from_node ? `${data.from_node} → human` : "agent → human",
          details: JSON.stringify(data.payload || {}, null, 2),
        });
        state.busy = false;
        els.runBtn.disabled = false;
        break;

      case "final":
        hideHitl();
        hideHandoff();
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
        state.steps.forEach((step) => {
          if (step.status === "active") step.status = "done";
        });
        upsertStep({
          id: `final-${Date.now()}`,
          kind: "agent",
          agent: "complete",
          title: "Complete",
          status: "done",
          time: formatTime(),
          summary: `Compliance: ${verdict}`,
          details: data.report || "",
        });
        setCurrentAgent("complete", "done", `Run finished · compliance ${verdict}`);
        setStatus("done", "Complete");
        break;

      case "done":
        state.busy = false;
        els.runBtn.disabled = false;
        break;

      case "error":
        setStatus("error", "Error");
        setCurrentAgent("error", "blocked", data.message || "Run failed");
        upsertStep({
          id: `error-${Date.now()}`,
          kind: "agent",
          agent: "error",
          title: "Error",
          status: "blocked",
          time: formatTime(),
          summary: data.message || "Unknown error",
          details: data.message || "",
        });
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
    resetSteps();
    if (els.timeline) els.timeline.innerHTML = "";
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
          autonomy_level: state.autonomyLevel,
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
    showHandoff("human", state.lastAgent || "agent", `Resume: ${decision.trim()}`);

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
    state.autonomyLevels = data.governance?.levels || [];
    state.autonomyLevel = data.default_autonomy_level || "L2";
    els.autonomySelect.innerHTML = "";
    state.autonomyLevels.forEach((level) => {
      const option = document.createElement("option");
      option.value = level.id;
      option.textContent = `${level.id} · ${level.name}`;
      els.autonomySelect.appendChild(option);
    });
    els.autonomySelect.value = state.autonomyLevel;
    applyAutonomy(state.autonomyLevel);
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
  els.autonomySelect.addEventListener("change", () => {
    applyAutonomy(els.autonomySelect.value);
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
