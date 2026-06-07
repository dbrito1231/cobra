import { ChatPanel } from "./chat.js";
import { WikiPanel } from "./wiki.js";
import { StatusPanel } from "./status.js";
import { SearchOverlay } from "./search.js";
import { WebSocketClient } from "./websocket.js";

const chat = new ChatPanel(
  document.getElementById("chat-history"),
  document.getElementById("chat-form"),
  document.getElementById("chat-input")
);

const wiki = new WikiPanel(
  document.getElementById("wiki-content"),
  document.getElementById("wiki-title"),
  document.getElementById("wiki-back")
);

const status = new StatusPanel({
  pipelineLabel: document.getElementById("pipeline-label"),
  pipelineElapsed: document.getElementById("pipeline-elapsed"),
  pipelineStatus: document.getElementById("pipeline-status"),
  mcpList: document.getElementById("mcp-list"),
  healthList: document.getElementById("health-list"),
  proactiveCount: document.getElementById("proactive-count"),
  proactivePreview: document.getElementById("proactive-preview"),
  tellMeNowBtn: document.getElementById("tell-me-now"),
  voiceIndicator: document.getElementById("voice-indicator"),
  voiceLabel: document.getElementById("voice-label"),
  profileName: document.getElementById("profile-name"),
});

const lockOverlay = document.getElementById("lock-overlay");
const lmStudioBanner = document.getElementById("lm-studio-banner");
const lmStudioMessage = document.getElementById("lm-studio-message");
const seedBanner = document.getElementById("seed-banner");
const seedBannerResume = document.getElementById("seed-banner-resume");
const chatInput = document.getElementById("chat-input");
const sendButton = document.getElementById("send-button");

const search = new SearchOverlay(
  document.getElementById("search-overlay"),
  document.getElementById("search-input"),
  document.getElementById("search-results"),
  document.getElementById("search-close")
);

const ws = new WebSocketClient("/ws");

chat.onSend = async (text) => {
  await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
};

chat.onApproval = async (eventId, approved) => {
  await fetch("/api/approval", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_id: eventId, approved }),
  });
};

chat.onFailure = async (eventId, action) => {
  await fetch("/api/failure", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_id: eventId, action }),
  });
};

document.getElementById("lm-studio-cancel").addEventListener("click", async () => {
  await fetch("/api/lm-studio/cancel", { method: "POST" });
});

function setLocked(locked) {
  lockOverlay.hidden = !locked;
  chatInput.disabled = locked;
  sendButton.disabled = locked;
}

function setLmStudioWait(waiting, message) {
  lmStudioBanner.hidden = !waiting;
  lmStudioMessage.textContent = message || "";
  if (waiting) seedBanner.hidden = true;
}

function setSeedMode(active, resumeLabel) {
  seedBanner.hidden = !active;
  seedBannerResume.textContent = active && resumeLabel ? `Resume: ${resumeLabel}` : "";
}

status.onTellMeNow = async () => {
  await fetch("/api/proactive/tell-me-now", { method: "POST" });
};

search.onJump = async (result) => {
  const currentSession = await fetch("/api/session/messages").then((r) => r.json());
  if (result.session_id && result.session_id !== currentSession.session_id) {
    const payload = await fetch(`/api/session/${encodeURIComponent(result.session_id)}/activate`, {
      method: "POST",
    }).then((r) => r.json());
    chat.loadHistory(payload.messages || []);
  }
  chat.jumpToMessage(result.message_id);
};

document.getElementById("search-button").addEventListener("click", () => search.open());

ws.on("status_snapshot", (payload) => {
  status.applySnapshot(payload);
  if (typeof payload.locked === "boolean") setLocked(payload.locked);
  if (typeof payload.lm_studio_waiting === "boolean") {
    setLmStudioWait(payload.lm_studio_waiting, payload.lm_studio_message);
  }
});

ws.on("component_health", (payload) => status.setComponentHealth(payload.components || []));

ws.on("failure_prompt", (payload) => chat.showFailureCard(payload));

ws.on("lock_state", (payload) => setLocked(Boolean(payload.locked)));

ws.on("anomaly_alert", (payload) => status.showAnomalyAlert(payload));

ws.on("lm_studio_wait", (payload) => setLmStudioWait(Boolean(payload.waiting), payload.message));

ws.on("seed_mode", (payload) => setSeedMode(Boolean(payload.active), payload.resume_label));

ws.on("seed_prompt", (payload) => chat.showSeedPrompt(payload));

ws.on("seed_confirm", (payload) => chat.showSeedConfirm(payload));

ws.on("seed_summary_review", (payload) => chat.showSeedSummaryReview(payload));

ws.on("config_notify", (payload) => status.showConfigNotify(payload.message));

ws.on("session_history", (payload) => {
  chat.loadHistory(payload.messages || []);
});

ws.on("message", (payload) => {
  chat.renderMessage(payload);
  if (payload.sender === "cobra") {
    chat.clearPipelineIndicators();
    status.setPipeline("idle", "Idle");
  }
});

ws.on("pipeline_step", (payload) => {
  status.setPipeline(payload.step, payload.label);
  chat.clearPipelineIndicators(payload.message_id);
  if (payload.step !== "idle") {
    chat.showInlinePipeline(payload.label, payload.message_id);
  }
});

ws.on("voice_state", (payload) => status.setVoiceState(payload.state));

ws.on("mcp_status", (payload) => status.setMcpServers(payload.servers || []));

ws.on("proactive_queue", (payload) => {
  status.setProactiveQueue(payload.count, payload.top_item);
});

ws.on("approval_request", (payload) => chat.showApprovalCard(payload));

ws.on("proactive_surfaced", (payload) => chat.showProactiveCard(payload));

ws.connect();
wiki.loadIndex().catch(console.error);

async function checkWizard() {
  const status = await fetch("/api/wizard/status").then((r) => r.json());
  const overlay = document.getElementById("wizard-overlay");
  if (status.needs_wizard) overlay.hidden = false;
}

document.getElementById("wizard-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = Object.fromEntries(new FormData(form).entries());
  const result = await fetch("/api/wizard/complete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) => r.json());
  if (result.status === "ok") {
    document.getElementById("wizard-overlay").hidden = true;
  } else {
    alert(result.message || "Wizard failed");
  }
});

checkWizard().catch(console.error);
