class ReelMatchApp {
  constructor() {
    this.ws = null;
    this.isConnected = false;
    this.sessionId = this.generateSessionId();

    this.currentAssistantMessage = null;

    this.initializeElements();
    this.setupEventListeners();
  }

  initializeElements() {
    this.connectBtn = document.getElementById("connectBtn");
    this.status = document.getElementById("status");
    this.messagesContent = document.getElementById("messagesContent");
    this.eventsContent = document.getElementById("eventsContent");
    this.toolsContent = document.getElementById("toolsContent");
    this.textInput = document.getElementById("textInput");
    this.sendBtn = document.getElementById("sendBtn");
  }

  setupEventListeners() {
    this._handleSendText = async () => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        console.warn("WebSocket not connected");
        return;
      }
      if (!this.textInput) {
        console.warn("Text input box not found");
        return;
      }

      const text = this.textInput.value.trim();
      if (!text) return;

      this.ws.send(
        JSON.stringify({
          type: "text",
          text: text,
        })
      );
      this.addMessage("user", text);
      this.textInput.value = "";

      this.currentAssistantMessage = null;
    };

    if (this.sendBtn && this.textInput) {
      this.sendBtn.addEventListener("click", () => this._handleSendText());

      this.textInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this._handleSendText();
        }
      });
    }

    this.connectBtn.addEventListener("click", () => {
      if (this.isConnected) {
        this.disconnect();
      } else {
        this.connect();
      }
    });
  }

  generateSessionId() {
    return "session_" + Math.random().toString(36).substr(2, 9);
  }

  async connect() {
    try {
      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsHost = window.location.host;
      this.ws = new WebSocket(`${wsProtocol}//${wsHost}/ws/${this.sessionId}`);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.updateConnectionUI();
        console.log("✅ Connected to WebSocket");
      };

      this.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("📨 Received event:", data);
        this.handleRealtimeEvent(data);
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        this.updateConnectionUI();
        console.log("🔌 WebSocket closed");
      };

      this.ws.onerror = (error) => {
        console.error("WebSocket error:", error);
      };
    } catch (error) {
      console.error("Failed to connect:", error);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }

  updateConnectionUI() {
    if (this.isConnected) {
      this.connectBtn.textContent = "Disconnect";
      this.connectBtn.className = "connect-btn connected";
      this.status.textContent = "Connected";
      this.status.className = "status connected";
    } else {
      this.connectBtn.textContent = "Connect";
      this.connectBtn.className = "connect-btn disconnected";
      this.status.textContent = "Disconnected";
      this.status.className = "status disconnected";
    }
  }

  addPartialAssistantMessage(delta) {
    if (!this.currentAssistantMessage) {
      this.currentAssistantMessage = this.addMessage("assistant", delta);
    } else {
      const bubble =
        this.currentAssistantMessage.querySelector(".message-bubble");
      if (bubble) {
        bubble.textContent += delta;
        this.scrollToBottom();
      }
    }
  }

  handleRealtimeEvent(event) {
    this.addRawEvent(event);

    // Add to tools panel if it's a tool or handoff event
    if (
      event.type === "tool_start" ||
      event.type === "tool_end" ||
      event.type === "handoff"
    ) {
      this.addToolEvent(event);
    }

    // Handle specific event types
    switch (event.type) {
      case "assistant_response_delta":
        // Streaming chunk (partial text)
        if (event.text) {
          this.addPartialAssistantMessage(event.text);
        }
        break;

      case "response_complete":
        // Response finished
        console.log("✅ Response complete");
        this.currentAssistantMessage = null;
        break;

      case "recommendations":
        this.addRecommendations(event.data);
        break;
    }
  }

  addRecommendations(data) {
    const list = document.createElement("div");
    list.className = "recommendations";

    data.recommendations.forEach((rec, i) => {
      const card = document.createElement("div");
      card.className = "recommendation-card";

      const title = document.createElement("div");
      title.className = "recommendation-title";
      title.textContent = `${i + 1}. ${rec.title} (${rec.release_date})`;

      const genre = document.createElement("div");
      genre.className = "recommendation-genre";
      genre.textContent = rec.genre;

      const theater = document.createElement("div");
      theater.className = "recommendation-theater";
      theater.textContent = `📍 ${rec.theater_name}, ${rec.theater_address}`;

      const showtimes = document.createElement("div");
      showtimes.className = "recommendation-showtimes";
      showtimes.textContent = `🕒 ${rec.showtimes.join(" · ")}`;

      const reason = document.createElement("div");
      reason.className = "recommendation-reason";
      reason.textContent = rec.reason;

      card.append(title, genre, theater, showtimes, reason);
      list.appendChild(card);
    });

    this.messagesContent.appendChild(list);
    if (data.closing_message) {
      this.addMessage("assistant", data.closing_message);
    }
    this.scrollToBottom();
  }

  addMessage(type, content) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${type}`;

    const bubbleDiv = document.createElement("div");
    bubbleDiv.className = "message-bubble";
    bubbleDiv.textContent = content;

    messageDiv.appendChild(bubbleDiv);
    this.messagesContent.appendChild(messageDiv);
    this.scrollToBottom();

    return messageDiv;
  }

  addRawEvent(event) {
    const eventDiv = document.createElement("div");
    eventDiv.className = "event";

    const headerDiv = document.createElement("div");
    headerDiv.className = "event-header";
    headerDiv.innerHTML = `
            <span>${event.type}</span>
            <span>▼</span>
        `;

    const contentDiv = document.createElement("div");
    contentDiv.className = "event-content collapsed";
    contentDiv.textContent = JSON.stringify(event, null, 2);

    headerDiv.addEventListener("click", () => {
      const isCollapsed = contentDiv.classList.contains("collapsed");
      contentDiv.classList.toggle("collapsed");
      headerDiv.querySelector("span:last-child").textContent = isCollapsed
        ? "▲"
        : "▼";
    });

    eventDiv.appendChild(headerDiv);
    eventDiv.appendChild(contentDiv);
    this.eventsContent.appendChild(eventDiv);

    this.eventsContent.scrollTop = this.eventsContent.scrollHeight;
  }

  addToolEvent(event) {
    const eventDiv = document.createElement("div");
    eventDiv.className = "event";

    let title = "";
    let description = "";
    let eventClass = "";

    if (event.type === "handoff") {
      title = `🔄 Handoff`;
      description = `From ${event.from} to ${event.to}`;
      eventClass = "handoff";
    } else if (event.type === "tool_start") {
      title = `🔧 Tool Started`;
      description = `Running ${event.tool}`;
      eventClass = "tool";
    } else if (event.type === "tool_end") {
      title = `✅ Tool Completed`;
      description = `${event.tool}: ${event.output || "No output"}`;
      eventClass = "tool";
    }

    eventDiv.innerHTML = `
            <div class="event-header ${eventClass}">
                <div>
                    <div style="font-weight: 600; margin-bottom: 2px;">${title}</div>
                    <div style="font-size: 0.8rem; opacity: 0.8;">${description}</div>
                </div>
                <span style="font-size: 0.7rem; opacity: 0.6;">${new Date().toLocaleTimeString()}</span>
            </div>
        `;

    this.toolsContent.appendChild(eventDiv);

    // Auto-scroll tools pane
    this.toolsContent.scrollTop = this.toolsContent.scrollHeight;
  }

  scrollToBottom() {
    this.messagesContent.scrollTop = this.messagesContent.scrollHeight;
  }
}

// Initialize the app when the page loads
document.addEventListener("DOMContentLoaded", () => {
  new ReelMatchApp();
});
