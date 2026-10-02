const API_BASE = window.location.origin;

function getAuthHeaders() {
  const token = localStorage.getItem("access_token");
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function apiFetch(url, options = {}) {
  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...getAuthHeaders(), ...options.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Erro ${response.status}`);
  }
  return response;
}

async function sendMessageStream({ message, history, session_id, onDelta, signal }) {
  const response = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ message, history, session_id }),
    signal,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body?.detail || "Erro ao enviar mensagem para o servidor.";
    throw new Error(detail);
  }

  if (!response.body) {
    throw new Error("Streaming nao suportado no ambiente atual.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const rawEvent of events) {
      const line = rawEvent
        .split("\n")
        .find((part) => part.startsWith("data:"));
      if (!line) continue;

      const payloadText = line.slice(5).trim();
      if (!payloadText) continue;

      let payload;
      try {
        payload = JSON.parse(payloadText);
      } catch {
        continue;
      }

      if (payload.error) {
        throw new Error(payload.error);
      }

      if (payload.delta) {
        onDelta(payload.delta);
      }

      // Return session_id and title when done
      if (payload.done) {
        return { session_id: payload.session_id, title: payload.title };
      }
    }
  }
}

// Session API functions
async function listSessions() {
  const resp = await apiFetch("/api/sessions");
  const data = await resp.json();
  return data.sessions;
}

async function createSession() {
  const resp = await apiFetch("/api/sessions", { method: "POST", body: JSON.stringify({}) });
  return await resp.json();
}

async function getSessionMessages(sessionId) {
  const resp = await apiFetch(`/api/sessions/${sessionId}/messages`);
  return await resp.json();
}

async function deleteSession(sessionId) {
  await apiFetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
}

async function getInstructions() {
  const resp = await apiFetch("/api/instructions");
  return await resp.json();
}

async function saveInstructions(content) {
  const resp = await apiFetch("/api/instructions", { method: "PUT", body: JSON.stringify({ content }) });
  return await resp.json();
}

async function resetInstructions() {
  const resp = await apiFetch("/api/instructions", { method: "DELETE" });
  return await resp.json();
}