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
  proactiveCount: document.getElementById("proactive-count"),
  proactivePreview: document.getElementById("proactive-preview"),
  tellMeNowBtn: document.getElementById("tell-me-now"),
  voiceIndicator: document.getElementById("voice-indicator"),
  voiceLabel: document.getElementById("voice-label"),
  profileName: document.getElementById("profile-name"),
});

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

ws.on("status_snapshot", (payload) => status.applySnapshot(payload));

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
