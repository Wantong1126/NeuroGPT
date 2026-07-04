(() => {
  const form = document.getElementById("elder-report-form");
  const transcript = document.getElementById("elder-transcript");
  if (!form || !transcript || !window.fetch || !window.AbortController) return;

  const input = form.querySelector("textarea[name='user_input']");
  const submitButton = form.querySelector("button[type='submit']");
  let submitting = false;

  function appendTurn(role, text) {
    const turn = document.createElement("article");
    turn.className = `turn ${role === "user" ? "user-turn" : "assistant-turn"}`;
    const label = document.createElement("div");
    label.className = "turn-label";
    label.textContent = role === "user" ? "我" : "NeuroGPT";
    const body = document.createElement("div");
    body.className = "turn-body";
    body.textContent = text;
    turn.append(label, body);
    transcript.appendChild(turn);
    turn.scrollIntoView({ behavior: "smooth", block: "end" });
    return body;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitting) return;

    const message = input.value.trim();
    if (!message) return;

    submitting = true;
    appendTurn("user", message);
    const loadingBody = appendTurn("assistant", "正在帮您记录，请稍等……");
    input.value = "";
    submitButton.disabled = true;

    const controller = new AbortController();
    const slowTimer = window.setTimeout(() => {
      loadingBody.textContent = "还在整理，请稍等。如果现在很不舒服，请先叫护理员。";
      loadingBody.scrollIntoView({ behavior: "smooth", block: "end" });
    }, 8000);
    const abortTimer = window.setTimeout(() => controller.abort(), 15000);

    try {
      const response = await fetch(form.dataset.apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({
          resident_id: form.dataset.residentId,
          message,
        }),
        signal: controller.signal,
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) throw new Error(payload.error || "request failed");
      loadingBody.textContent = payload.elder_response;
    } catch (_error) {
      loadingBody.textContent = "我先帮您记录了这条信息。网络有点慢，如果现在很不舒服，请马上叫护理员。";
    } finally {
      window.clearTimeout(slowTimer);
      window.clearTimeout(abortTimer);
      submitButton.disabled = false;
      submitting = false;
      input.focus();
      loadingBody.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  });
})();
