export class WebSocketClient {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.handlers = new Map();
    this.reconnectDelay = 1000;
    this.shouldReconnect = true;
  }

  connect() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    this.ws = new WebSocket(`${protocol}//${location.host}${this.url}`);

    this.ws.addEventListener("open", () => {
      this.reconnectDelay = 1000;
    });

    this.ws.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);
        this.emit(data.type, data.payload);
      } catch {
        /* ignore malformed frames */
      }
    });

    this.ws.addEventListener("close", () => {
      if (this.shouldReconnect) {
        setTimeout(() => this.connect(), this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, 10000);
      }
    });
  }

  on(type, handler) {
    if (!this.handlers.has(type)) this.handlers.set(type, []);
    this.handlers.get(type).push(handler);
  }

  emit(type, payload) {
    (this.handlers.get(type) || []).forEach((fn) => fn(payload));
  }

  disconnect() {
    this.shouldReconnect = false;
    this.ws?.close();
  }
}
