import { createInlineIndicator } from "./pipeline.js";

const SLOW_THRESHOLD_MS = 3000;

export class ChatPanel {
  constructor(historyEl, formEl, inputEl) {
    this.historyEl = historyEl;
    this.formEl = formEl;
    this.inputEl = inputEl;
    this.pendingIndicators = new Map();
    this.inlineTimers = new Map();
    this.onSend = null;
    this.onApproval = null;
    this.onFailure = null;

    this.formEl.addEventListener("submit", (e) => this.handleSubmit(e));
    this.inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.formEl.requestSubmit();
      }
    });
  }

  handleSubmit(e) {
    e.preventDefault();
    const text = this.inputEl.value.trim();
    if (!text || !this.onSend) return;
    this.inputEl.value = "";
    this.onSend(text);
  }

  renderMessage(message) {
    const sender = message.sender === "user" ? "You" : "C.O.B.R.A.";
    const senderClass = message.sender === "user" ? "message-user" : "message-cobra";
    const time = formatTimestamp(message.timestamp);

    const el = document.createElement("div");
    el.className = `message ${senderClass}`;
    el.id = `msg-${message.id}`;
    el.dataset.messageId = message.id;
    el.innerHTML = `
      <div class="message-meta">${sender} · ${time}</div>
      <div class="message-content">${escapeHtml(message.content)}</div>
    `;
    this.historyEl.appendChild(el);
    this.scrollToBottom();
    return el;
  }

  loadHistory(messages) {
    this.historyEl.innerHTML = "";
    this.clearAllInlineTimers();
    messages.forEach((msg) => this.renderMessage(msg));
  }

  showInlinePipeline(label, messageId) {
    this.clearPipelineIndicators(messageId);
    const el = createInlineIndicator(label, messageId);
    this.historyEl.appendChild(el);
    if (messageId) this.pendingIndicators.set(messageId, el);
    this.startInlineElapsedTimer(el);
    this.scrollToBottom();
  }

  startInlineElapsedTimer(el) {
    const elapsedEl = el.querySelector(".pipeline-elapsed");
    const startedAt = Date.now();
    const timer = setInterval(() => {
      const elapsed = Date.now() - startedAt;
      if (elapsed >= SLOW_THRESHOLD_MS && elapsedEl) {
        elapsedEl.textContent = `${Math.floor(elapsed / 1000)}s`;
        elapsedEl.hidden = false;
      }
    }, 1000);
    this.inlineTimers.set(el, timer);
  }

  clearAllInlineTimers() {
    this.inlineTimers.forEach((timer) => clearInterval(timer));
    this.inlineTimers.clear();
  }

  clearPipelineIndicators(messageId) {
    const selector = messageId
      ? `.pipeline-indicator[data-message-id="${messageId}"]`
      : ".pipeline-indicator";
    this.historyEl.querySelectorAll(selector).forEach((el) => {
      const timer = this.inlineTimers.get(el);
      if (timer) {
        clearInterval(timer);
        this.inlineTimers.delete(el);
      }
      el.remove();
    });
    if (messageId) this.pendingIndicators.delete(messageId);
  }

  showApprovalCard(request) {
    const el = document.createElement("div");
    el.className = "approval-card";
    el.dataset.eventId = request.event_id;

    let extraFields = "";
    if (request.code_preview) {
      extraFields += `
        <div class="approval-field"><strong>Code preview</strong>
          <pre class="code-preview">${escapeHtml(request.code_preview)}</pre>
        </div>`;
    }
    if (request.draft_content) {
      extraFields += `
        <div class="approval-field"><strong>Draft</strong>
          <pre class="draft-preview">${escapeHtml(request.draft_content)}</pre>
        </div>`;
    }

    el.innerHTML = `
      <h4>Approval Required</h4>
      <div class="approval-field"><strong>What</strong>${escapeHtml(request.what)}</div>
      <div class="approval-field"><strong>Why</strong>${escapeHtml(request.why)}</div>
      <div class="approval-field"><strong>Data involved</strong>${escapeHtml(request.data_summary)}</div>
      ${extraFields}
      <div class="approval-actions">
        <button class="btn btn-approve" data-action="approve">Approve</button>
        <button class="btn btn-deny" data-action="deny">Deny</button>
      </div>
    `;

    el.querySelector('[data-action="approve"]').addEventListener("click", () => {
      this.onApproval?.(request.event_id, true);
      el.remove();
    });
    el.querySelector('[data-action="deny"]').addEventListener("click", () => {
      this.onApproval?.(request.event_id, false);
      el.remove();
    });

    this.historyEl.appendChild(el);
    this.scrollToBottom();
  }

  showFailureCard(request) {
    const el = document.createElement("div");
    el.className = "failure-card";
    el.dataset.eventId = request.event_id;
    el.innerHTML = `
      <h4>Component Failure</h4>
      <div class="approval-field"><strong>Component</strong>${escapeHtml(request.component)}</div>
      <div class="approval-field"><strong>State</strong>${escapeHtml(request.state)}</div>
      <div class="approval-field"><strong>Details</strong>${escapeHtml(request.message)}</div>
      <div class="approval-actions">
        <button class="btn btn-approve" data-action="restart_component">Restart</button>
        <button class="btn btn-deny" data-action="ignore">Ignore</button>
        <button class="btn btn-accent" data-action="restart_all">Restart All</button>
      </div>
    `;
    el.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        this.onFailure?.(request.event_id, btn.dataset.action);
        el.remove();
      });
    });
    this.historyEl.appendChild(el);
    this.scrollToBottom();
  }

  showProactiveCard(item) {
    const el = document.createElement("div");
    el.className = "proactive-card";
    el.innerHTML = `
      <h4>Proactive Item</h4>
      <p>${escapeHtml(item.preview)}</p>
    `;
    this.historyEl.appendChild(el);
    this.scrollToBottom();
  }

  showSeedPrompt(payload) {
    const el = document.createElement("div");
    el.className = "seed-card";
    el.innerHTML = `
      <h4>Personality Interview</h4>
      <div class="seed-stage">${escapeHtml(payload.stage || "")}</div>
      <p>${escapeHtml(payload.content || "")}</p>
      ${payload.question ? `<p><strong>Question:</strong> ${escapeHtml(payload.question)}</p>` : ""}
    `;
    this.historyEl.appendChild(el);
    this.scrollToBottom();
  }

  showSeedConfirm(payload) {
    const el = document.createElement("div");
    el.className = "seed-card";
    el.innerHTML = `
      <h4>Confirm Understanding</h4>
      <div class="seed-stage">${escapeHtml(payload.stage || "")}</div>
      <p>${escapeHtml(payload.reflection || "")}</p>
      <p><em>${escapeHtml(payload.question || "Does that capture what you meant?")}</em></p>
      <div class="approval-actions">
        <button class="btn btn-approve" data-action="yes">Yes</button>
        <button class="btn btn-deny" data-action="no">No</button>
      </div>
    `;
    el.querySelector('[data-action="yes"]').addEventListener("click", () => {
      this.onSend?.("yes");
    });
    el.querySelector('[data-action="no"]').addEventListener("click", () => {
      this.onSend?.("no");
    });
    this.historyEl.appendChild(el);
    this.scrollToBottom();
  }

  showSeedSummaryReview(payload) {
    const el = document.createElement("div");
    el.className = "seed-card";
    el.innerHTML = `
      <h4>Review Summary</h4>
      <div class="seed-stage">${escapeHtml(payload.stage || "")}</div>
      <p>${escapeHtml(payload.summary || "")}</p>
      <p><em>${escapeHtml(payload.prompt || "Reply approve to save or send edits.")}</em></p>
      <div class="approval-actions">
        <button class="btn btn-approve" data-action="approve">Approve</button>
      </div>
    `;
    el.querySelector('[data-action="approve"]').addEventListener("click", () => {
      this.onSend?.("approve");
    });
    this.historyEl.appendChild(el);
    this.scrollToBottom();
  }

  jumpToMessage(messageId) {
    const el = document.getElementById(`msg-${messageId}`);
    if (!el) return false;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("highlight");
    setTimeout(() => el.classList.remove("highlight"), 2500);
    return true;
  }

  scrollToBottom() {
    this.historyEl.scrollTop = this.historyEl.scrollHeight;
  }
}

function formatTimestamp(iso) {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
