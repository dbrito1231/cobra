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
const seedBannerMessage = document.getElementById("seed-banner-message");
const seedBannerResume = document.getElementById("seed-banner-resume");
const seedBannerAction = document.getElementById("seed-banner-action");
const chatInput = document.getElementById("chat-input");
const sendButton = document.getElementById("send-button");
const onboardingOverlay = document.getElementById("onboarding-overlay");
const onboardingVoicePanel = document.getElementById("onboarding-voice-panel");
const onboardingSeedPanel = document.getElementById("onboarding-seed-panel");
const onboardingCompletePanel = document.getElementById("onboarding-complete-panel");
const voiceEnrollmentPrompt = document.getElementById("voice-enrollment-prompt");
const voiceEnrollmentProgress = document.getElementById("voice-enrollment-progress");
const voiceEnrollmentProgressLabel = document.getElementById("voice-enrollment-progress-label");
const voiceEnrollmentStatus = document.getElementById("voice-enrollment-status");
const voiceRecordStart = document.getElementById("voice-record-start");
const voiceRecordStop = document.getElementById("voice-record-stop");
const voiceTrainBtn = document.getElementById("voice-train");
const voiceTestPlaybackBtn = document.getElementById("voice-test-playback");
const voiceApproveBtn = document.getElementById("voice-approve");
const voiceRejectBtn = document.getElementById("voice-reject");
const onboardingStartSeedBtn = document.getElementById("onboarding-start-seed");
const onboardingFinishBtn = document.getElementById("onboarding-finish");

let onboardingState = { phase: "complete", operational: true };
let mediaRecorder = null;
let recordedChunks = [];
let recordStartTime = 0;

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

function setChatBlocked(blocked) {
  const onboardingActive = blocked && !onboardingState.operational;
  chatInput.disabled = blocked;
  sendButton.disabled = blocked;
  if (onboardingActive) {
    onboardingOverlay.hidden = false;
  } else if (onboardingState.operational) {
    onboardingOverlay.hidden = true;
  }
}

function setLocked(locked) {
  lockOverlay.hidden = !locked;
  if (locked) {
    chatInput.disabled = true;
    sendButton.disabled = true;
  } else if (!onboardingState.operational) {
    setChatBlocked(true);
  } else {
    chatInput.disabled = false;
    sendButton.disabled = false;
  }
}

function updateOnboardingSteps(phase) {
  document.querySelectorAll(".onboarding-step").forEach((el) => {
    const step = el.dataset.step;
    el.classList.remove("active", "done");
    const order = ["config", "voice", "seed", "complete"];
    const phaseIndex = order.indexOf(phase);
    const stepIndex = order.indexOf(step);
    if (stepIndex < phaseIndex || phase === "complete") el.classList.add("done");
    if (step === phase) el.classList.add("active");
    if (phase === "complete" && step === "complete") {
      el.classList.add("active");
      el.classList.add("done");
    }
  });
}

function showOnboardingPanel(phase) {
  onboardingVoicePanel.hidden = phase !== "voice";
  onboardingSeedPanel.hidden = phase !== "seed";
  onboardingCompletePanel.hidden = phase !== "complete";
  updateOnboardingSteps(phase);
}

async function refreshVoiceEnrollmentStatus() {
  const status = await fetch("/api/voice/enrollment/status").then((r) => r.json());
  voiceEnrollmentPrompt.textContent = status.prompt || "All prompts recorded.";
  voiceEnrollmentProgress.max = status.minimum_seconds || 900;
  voiceEnrollmentProgress.value = status.sample_seconds || 0;
  const mins = Math.floor((status.sample_seconds || 0) / 60);
  const minGoal = Math.floor((status.minimum_seconds || 900) / 60);
  voiceEnrollmentProgressLabel.textContent = `${mins} / ${minGoal} min minimum`;
  voiceTrainBtn.disabled = !status.minimum_met || !status.tts_available;
  voiceTestPlaybackBtn.disabled = !status.trained || !status.tts_available;
  voiceApproveBtn.disabled = !status.trained || !status.tts_available;
  voiceRejectBtn.disabled = !status.trained;
  voiceRecordStart.disabled = !status.tts_available;
  if (!status.tts_available) {
    voiceEnrollmentStatus.textContent =
      status.install_instructions || "Install Coqui TTS (pip install -r requirements-voice.txt) to continue.";
  } else if (status.complete) {
    voiceEnrollmentStatus.textContent = "Voice enrollment complete.";
  } else if (status.trained) {
    voiceEnrollmentStatus.textContent = "Listen to the test playback, then approve or record more.";
  } else if (status.minimum_met) {
    voiceEnrollmentStatus.textContent = "Minimum reached — train your voice model.";
  } else {
    voiceEnrollmentStatus.textContent = "Record each prompt clearly at a natural pace.";
  }
  return status;
}

function applyOnboarding(payload) {
  onboardingState = {
    phase: payload.phase || "complete",
    operational: Boolean(payload.operational),
    voice_complete: Boolean(payload.voice_complete),
    personality_complete: Boolean(payload.personality_complete),
  };
  if (onboardingState.operational) {
    onboardingOverlay.hidden = true;
    setChatBlocked(false);
    seedBanner.hidden = true;
    return;
  }
  showOnboardingPanel(onboardingState.phase);
  setChatBlocked(true);
  if (onboardingState.phase === "voice") {
    refreshVoiceEnrollmentStatus().catch(console.error);
  }
  if (onboardingState.phase === "seed") {
    seedBanner.hidden = false;
    setSeedMode({
      active: true,
      mvp_complete: false,
      optional_remaining: true,
      resume_label: "Personality interview",
    });
  }
}

async function blobToBase64(blob) {
  const buffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  bytes.forEach((b) => {
    binary += String.fromCharCode(b);
  });
  return btoa(binary);
}

voiceRecordStart.addEventListener("click", async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordedChunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) recordedChunks.push(event.data);
    };
    mediaRecorder.start();
    recordStartTime = Date.now();
    voiceRecordStart.hidden = true;
    voiceRecordStop.hidden = false;
    voiceEnrollmentStatus.textContent = "Recording… read the prompt aloud, then stop.";
  } catch (err) {
    voiceEnrollmentStatus.textContent = "Microphone access denied or unavailable.";
    console.error(err);
  }
});

voiceRecordStop.addEventListener("click", async () => {
  if (!mediaRecorder) return;
  const recorder = mediaRecorder;
  recorder.onstop = async () => {
    const blob = new Blob(recordedChunks, { type: "audio/webm" });
    const audioBase64 = await blobToBase64(blob);
    const durationSeconds = (Date.now() - recordStartTime) / 1000;
    await fetch("/api/voice/enrollment/sample", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audio_base64: audioBase64, duration_seconds: durationSeconds }),
    });
    recorder.stream.getTracks().forEach((track) => track.stop());
    mediaRecorder = null;
    voiceRecordStart.hidden = false;
    voiceRecordStop.hidden = true;
    await refreshVoiceEnrollmentStatus();
    const onboarding = await fetch("/api/onboarding/status").then((r) => r.json());
    applyOnboarding(onboarding);
  };
  recorder.stop();
});

voiceTrainBtn.addEventListener("click", async () => {
  await fetch("/api/voice/enrollment/train", { method: "POST" });
  await refreshVoiceEnrollmentStatus();
});

voiceTestPlaybackBtn.addEventListener("click", async () => {
  const result = await fetch("/api/voice/enrollment/test-playback", { method: "POST" }).then((r) =>
    r.json()
  );
  if (!result.audio_base64) return;
  const audio = new Audio(`data:audio/wav;base64,${result.audio_base64}`);
  audio.play().catch(console.error);
});

voiceApproveBtn.addEventListener("click", async () => {
  await fetch("/api/voice/enrollment/approve", { method: "POST" });
  const onboarding = await fetch("/api/onboarding/status").then((r) => r.json());
  applyOnboarding(onboarding);
});

voiceRejectBtn.addEventListener("click", async () => {
  await fetch("/api/voice/enrollment/reject", { method: "POST" });
  await refreshVoiceEnrollmentStatus();
});

onboardingStartSeedBtn.addEventListener("click", () => {
  onboardingOverlay.hidden = true;
  chat.onSend?.("start personality interview");
});

onboardingFinishBtn.addEventListener("click", () => {
  onboardingOverlay.hidden = true;
  setChatBlocked(false);
});

function setLmStudioWait(waiting, message) {
  lmStudioBanner.hidden = !waiting;
  lmStudioMessage.textContent = message || "";
  if (waiting) seedBanner.hidden = true;
}

function setSeedMode(payload) {
  const active = Boolean(payload?.active);
  seedBanner.hidden = !active;
  const mvpComplete = Boolean(payload?.mvp_complete);
  const optionalRemaining = Boolean(payload?.optional_remaining);
  const hasResume = Boolean(payload?.resume_label);
  if (active && mvpComplete && optionalRemaining) {
    seedBannerMessage.textContent =
      "Your personality model is active. Complete the optional profile interview when you have time.";
    seedBannerAction.textContent = "Continue interview";
    seedBannerAction.hidden = false;
  } else if (active && hasResume && mvpComplete === false && payload?.phase === "asking") {
    seedBannerMessage.textContent =
      "Complete the personality interview so C.O.B.R.A. can mirror your voice.";
    seedBannerAction.textContent = "Resume interview";
    seedBannerAction.hidden = false;
  } else if (active) {
    seedBannerMessage.textContent =
      "Complete the personality interview so C.O.B.R.A. can mirror your voice.";
    seedBannerAction.textContent = hasResume ? "Resume interview" : "Start interview";
    seedBannerAction.hidden = false;
  } else {
    seedBannerAction.hidden = true;
  }
  seedBannerResume.textContent =
    active && payload?.resume_label ? `Resume: ${payload.resume_label}` : "";
}

seedBannerAction.addEventListener("click", () => {
  const label = seedBannerAction.textContent || "";
  const text =
    label === "Continue interview" || label === "Resume interview"
      ? "continue personality interview"
      : "start personality interview";
  chat.onSend?.(text);
});

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

ws.on("onboarding_step", (payload) => applyOnboarding(payload));

ws.on("seed_mode", (payload) => {
  setSeedMode(payload);
  if (payload.profile_complete) {
    applyOnboarding({
      phase: "complete",
      operational: true,
      voice_complete: true,
      personality_complete: true,
    });
  }
});

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
    const onboarding = await fetch("/api/onboarding/status").then((r) => r.json());
    applyOnboarding(onboarding);
  } else {
    alert(result.message || "Wizard failed");
  }
});

checkWizard().catch(console.error);

async function checkOnboarding() {
  try {
    const status = await fetch("/api/onboarding/status").then((r) => r.json());
    applyOnboarding(status);
  } catch {
    /* onboarding unavailable before orchestrator starts */
  }
}

checkOnboarding().catch(console.error);

async function checkSeedStatus() {
  try {
    const status = await fetch("/api/seed/status").then((r) => r.json());
    if (status.profile_complete) return;
    const onboarding = await fetch("/api/onboarding/status").then((r) => r.json()).catch(() => null);
    if (onboarding && !onboarding.operational && onboarding.phase === "seed") {
      applyOnboarding(onboarding);
      return;
    }
    if (!status.mvp_complete || status.optional_remaining || !status.profile_complete) {
      setSeedMode({
        active: true,
        mvp_complete: Boolean(status.mvp_complete),
        optional_remaining: Boolean(status.optional_remaining),
        resume_label: status.resume_label || "",
      });
    }
  } catch {
    /* seed status unavailable before orchestrator starts */
  }
}

checkSeedStatus().catch(console.error);
