let currentSessionId = null;

const form = document.querySelector("#chatForm");
const input = document.querySelector("#messageInput");
const transcript = document.querySelector("#transcript");
const statusArea = document.querySelector("#status");
const resetButton = document.querySelector("#resetButton");
const sendButton = document.querySelector("#sendButton");

function setStatus(message) {
  statusArea.textContent = message;
}

function appendUserTurn(message) {
  const template = document.querySelector("#userTurnTemplate");
  const node = template.content.cloneNode(true);
  node.querySelector(".turn-body").textContent = message;
  transcript.appendChild(node);
}

function appendAssistantTurn(payload) {
  const template = document.querySelector("#assistantTurnTemplate");
  const node = template.content.cloneNode(true);

  node.querySelector(".action-banner").textContent =
    payload.next_action_label || payload.action_level || "Review response";
  node.querySelector(".main-message").textContent = payload.user_message || "";

  if (payload.follow_up_question) {
    const followUp = node.querySelector(".follow-up");
    followUp.hidden = false;
    followUp.querySelector("p").textContent = payload.follow_up_question;
  }

  if (payload.guidance_snippets && payload.guidance_snippets.length > 0) {
    const guidance = node.querySelector(".guidance");
    const list = guidance.querySelector("ul");
    guidance.hidden = false;
    payload.guidance_snippets.forEach((snippet) => {
      const item = document.createElement("li");
      item.textContent = snippet;
      list.appendChild(item);
    });
  }

  if (payload.caregiver_summary) {
    const caregiver = node.querySelector(".caregiver");
    caregiver.hidden = false;
    caregiver.querySelector("p").textContent = payload.caregiver_summary;
  }

  if (payload.disclaimer) {
    node.querySelector(".disclaimer").textContent = payload.disclaimer;
  }

  node.querySelector(".debug-panel pre").textContent = JSON.stringify(
    payload.debug_metadata || {},
    null,
    2
  );

  transcript.appendChild(node);
  transcript.scrollTop = transcript.scrollHeight;
}

async function sendMessage(message) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: currentSessionId,
      message,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || "Request failed");
  }

  return response.json();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) {
    return;
  }

  appendUserTurn(message);
  input.value = "";
  sendButton.disabled = true;
  setStatus("Sending...");

  try {
    const data = await sendMessage(message);
    currentSessionId = data.session_id;
    appendAssistantTurn(data.payload);
    setStatus(`Session: ${currentSessionId}`);
  } catch (error) {
    setStatus(`Error: ${error.message}`);
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
});

resetButton.addEventListener("click", async () => {
  const sessionId = currentSessionId;
  transcript.replaceChildren();
  currentSessionId = null;
  input.value = "";

  if (sessionId) {
    await fetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    }).catch(() => undefined);
  }

  setStatus("Reset. Ready.");
  input.focus();
});
