class RealtimeDemo {
  constructor() {
    this.ws = null;
    this.isConnected = false;
    this.stream = null;
    this.sessionId = this.generateSessionId();

    this.messageNodes = new Map(); 
    this.seenItemIds = new Set(); 
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

  completeAssistantMessage(text) {
    if (this.currentAssistantMessage) {
      const bubble =
        this.currentAssistantMessage.querySelector(".message-bubble");
      if (bubble && text) {
        bubble.textContent = text;
      }
      this.currentAssistantMessage = null;
    } else {
      this.addMessage("assistant", text);
    }
    this.scrollToBottom();
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

      case "assistant_response":
        // Complete response
        if (event.text) {
          this.completeAssistantMessage(event.text);
        }
        break;

      case "response_complete":
        // Response finished
        console.log("✅ Response complete");
        this.currentAssistantMessage = null;
        break;
      
      case "history_updated":
        this.syncMissingFromHistory(event.history);
        this.updateLastMessageFromHistory(event.history);
        break;

      case "history_added":
        if (event.item) {
          this.addMessageFromItem(event.item);
        }
        break;
    }
  }
  updateLastMessageFromHistory(history) {
    if (!history || !Array.isArray(history) || history.length === 0) return;
    // Find the last message item in history
    let last = null;
    for (let i = history.length - 1; i >= 0; i--) {
      const it = history[i];
      if (it && it.type === "message") {
        last = it;
        break;
      }
    }
    if (!last) return;

    const itemId = last.item_id;
    let text = "";

    if (Array.isArray(last.content)) {
      for (const part of last.content) {
        if (!part || typeof part !== "object") continue;
        if (part.type === "text" && part.text) text += part.text;
        else if (part.type === "input_text" && part.text) text += part.text;
        else if (
          (part.type === "input_audio" || part.type === "audio") &&
          part.transcript
        )
          text += part.transcript;
      }
    }

    const node = this.messageNodes.get(itemId);
    if (!node) {
      this.addMessageFromItem(last);
      return;
    }

    const bubble = node.querySelector(".message-bubble");
    if (bubble && text && text.trim()) {
      bubble.textContent = text.trim();
      this.scrollToBottom();
    }
  }

  syncMissingFromHistory(history) {
    if (!history || !Array.isArray(history)) return;
    for (const item of history) {
      if (!item || item.type !== "message") continue;
      const id = item.item_id;
      if (!id) continue;
      if (!this.seenItemIds.has(id)) {
        this.addMessageFromItem(item);
      }
    }
  }

  addMessageFromItem(item) {
    try {
      if (!item || item.type !== "message") return;
      let content = "";

      if (Array.isArray(item.content)) {
        for (const contentPart of item.content) {
          if (!contentPart || typeof contentPart !== "object") continue;
          if (contentPart.type === "text" && contentPart.text) {
            content += contentPart.text;
          } else if (contentPart.type === "input_text" && contentPart.text) {
            content += contentPart.text;
          }
        }
      }

      if (content) {
        const role = item.role === "user" ? "user" : "assistant";
        const node = this.addMessage(role, content);

        if (node && item.item_id) {
          this.messageNodes.set(item.item_id, node);
          this.seenItemIds.add(item.item_id);
        }
      }
    } catch (e) {
      console.error("Failed to add message from item:", e, item);
    }
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

// Initialize the demo when the page loads
document.addEventListener("DOMContentLoaded", () => {
  new RealtimeDemo();
});
