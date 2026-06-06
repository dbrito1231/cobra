const SLOW_THRESHOLD_MS = 3000;

export class PipelineTracker {
  constructor(labelEl, elapsedEl, statusEl) {
    this.labelEl = labelEl;
    this.elapsedEl = elapsedEl;
    this.statusEl = statusEl;
    this.startedAt = null;
    this.timer = null;
  }

  setStep(step, label) {
    this.clearTimer();
    this.labelEl.textContent = label || "Idle";
    const isIdle = !step || step === "idle";
    this.statusEl.classList.toggle("idle", isIdle);

    if (isIdle) {
      this.elapsedEl.hidden = true;
      this.startedAt = null;
      return;
    }

    this.startedAt = Date.now();
    this.elapsedEl.hidden = true;
    this.timer = setInterval(() => this.tick(), 1000);
  }

  tick() {
    if (!this.startedAt) return;
    const elapsed = Date.now() - this.startedAt;
    if (elapsed >= SLOW_THRESHOLD_MS) {
      const seconds = Math.floor(elapsed / 1000);
      this.elapsedEl.textContent = `${seconds}s`;
      this.elapsedEl.hidden = false;
    }
  }

  clearTimer() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}

export function createInlineIndicator(label, messageId) {
  const el = document.createElement("div");
  el.className = "pipeline-indicator";
  el.dataset.messageId = messageId || "";
  el.innerHTML = `<span class="pipeline-label">${label}</span><span class="pipeline-elapsed" hidden></span>`;
  return el;
}

export function removeInlineIndicators(container, messageId) {
  const selector = messageId
    ? `.pipeline-indicator[data-message-id="${messageId}"]`
    : ".pipeline-indicator";
  container.querySelectorAll(selector).forEach((el) => el.remove());
}
