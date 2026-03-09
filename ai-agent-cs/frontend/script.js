// Decide API base depending on how you're running the app.
// - Local dev with separate frontend (localhost:3000) + backend (localhost:8000)
//   -> call backend on http://localhost:8000
// - Single server (FastAPI serving frontend + backend on same port, e.g. 8000 or ngrok URL)
//   -> use same origin ("") so /chat, /health go to the same host/port.
let API_BASE = "";
if (
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
) {
  if (window.location.port === "3000") {
    API_BASE = "http://localhost:8000";
  } else {
    // e.g. localhost:8000 → same origin is fine
    API_BASE = "";
  }
}

const chatMessages = document.getElementById("chatMessages");
const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const typingIndicator = document.getElementById("typingIndicator");
const statusMessage = document.getElementById("statusMessage");

// Send message function
async function sendMessage() {
  const message = messageInput.value.trim();
  if (!message) return;

  // Add user message
  addMessage(message, "user");
  messageInput.value = "";

  // Show typing indicator
  typingIndicator.classList.add("show");

  // Disable input while processing
  sendButton.disabled = true;
  messageInput.disabled = true;

  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: message,
        session_id: "web_client_" + Date.now(),
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    // Hide typing indicator
    typingIndicator.classList.remove("show");

    // Add bot response
    addMessage(data.response, "bot", data.confidence, data.needs_escalation);

    // Show status if escalation needed
    if (data.needs_escalation) {
      showStatus("This query may need human assistance", "error");
    }
  } catch (error) {
    console.error("Error:", error);
    typingIndicator.classList.remove("show");
    addMessage("Sorry, I encountered an error. Please try again.", "bot", 0);
    showStatus("Connection error - check if backend is running", "error");
  } finally {
    // Re-enable input
    sendButton.disabled = false;
    messageInput.disabled = false;
    messageInput.focus();
  }
}

// Add message to chat
function addMessage(text, sender, confidence = null, needsEscalation = false) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${sender}`;

  // Add message text
  messageDiv.textContent = text;

  // Add confidence for bot messages
  if (sender === "bot" && confidence !== null) {
    const confidenceDiv = document.createElement("div");
    confidenceDiv.className = "confidence";
    confidenceDiv.textContent = `Confidence: ${confidence.toFixed(2)}${
      needsEscalation ? " ⚠️ May need escalation" : ""
    }`;
    messageDiv.appendChild(confidenceDiv);
  }

  chatMessages.appendChild(messageDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Show status message
function showStatus(text, type) {
  statusMessage.textContent = text;
  statusMessage.className = `status ${type}`;
  statusMessage.style.display = "block";

  setTimeout(() => {
    statusMessage.style.display = "none";
  }, 5000);
}

// Event listeners
sendButton.addEventListener("click", sendMessage);

messageInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Focus input on load & test connection
window.addEventListener("load", () => {
  messageInput.focus();
});

window.addEventListener("load", async () => {
  try {
    const response = await fetch(`${API_BASE}/health`);
    if (response.ok) {
      showStatus("Connected to AI backend", "success");
    } else {
      showStatus("Backend connection failed", "error");
    }
  } catch (error) {
    showStatus("Cannot connect to backend - start the server first", "error");
  }
});
