import { PipelineTracker } from "./pipeline.js";

export class StatusPanel {
  constructor(elements) {
    this.pipelineLabel = elements.pipelineLabel;
    this.pipelineElapsed = elements.pipelineElapsed;
    this.pipelineStatus = elements.pipelineStatus;
    this.mcpList = elements.mcpList;
    this.proactiveCount = elements.proactiveCount;
    this.proactivePreview = elements.proactivePreview;
    this.tellMeNowBtn = elements.tellMeNowBtn;
    this.voiceIndicator = elements.voiceIndicator;
    this.voiceLabel = elements.voiceLabel;
    this.profileName = elements.profileName;

    this.pipeline = new PipelineTracker(
      this.pipelineLabel,
      this.pipelineElapsed,
      this.pipelineStatus
    );
    this.onTellMeNow = null;

    this.tellMeNowBtn.addEventListener("click", () => this.onTellMeNow?.());
  }

  applySnapshot(payload) {
    if (payload.profile_name) {
      this.profileName.textContent = payload.profile_name;
    }
    this.setPipeline(payload.pipeline_step, payload.pipeline_label);
    this.setVoiceState(payload.voice_state);
    this.setMcpServers(payload.mcp_servers || []);
    this.setProactiveQueue(payload.proactive_count, payload.proactive_top);
  }

  setPipeline(step, label) {
    this.pipeline.setStep(step, label);
  }

  setVoiceState(state) {
    const labels = { idle: "Idle", listening: "Listening", speaking: "Speaking" };
    this.voiceIndicator.className = `voice-indicator voice-${state || "idle"}`;
    this.voiceLabel.textContent = labels[state] || "Idle";
    this.voiceIndicator.title = `Voice: ${labels[state] || "Idle"}`;
  }

  setMcpServers(servers) {
    this.mcpList.innerHTML = "";
    if (!servers.length) {
      this.mcpList.innerHTML = '<li class="mcp-empty">No MCP servers configured</li>';
      return;
    }
    servers.forEach((server) => {
      const li = document.createElement("li");
      li.innerHTML = `
        <span>${escapeHtml(server.name)}</span>
        <span class="mcp-status ${server.status}">${server.status}</span>
      `;
      this.mcpList.appendChild(li);
    });
  }

  setProactiveQueue(count, topItem) {
    this.proactiveCount.textContent = `${count} item${count === 1 ? "" : "s"} queued`;
    this.proactivePreview.textContent = topItem?.preview || "No items waiting";
    this.tellMeNowBtn.disabled = count === 0;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
