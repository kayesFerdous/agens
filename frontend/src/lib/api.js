export async function createSession(title) {
  const res = await fetch('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title })
  });
  return res.json();
}

export async function getSessions({ limit = 20, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (limit !== undefined) params.append('limit', limit);
  if (offset !== undefined) params.append('offset', offset);
  const query = params.toString();
  
  const res = await fetch(`/sessions${query ? `?${query}` : ''}`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to fetch sessions');
  }
  return res.json();
}

export async function getSession(sessionId) {
  const res = await fetch(`/sessions/${sessionId}`);
  if (!res.ok) return null;
  return res.json();
}

export async function deleteSession(sessionId) {
  await fetch(`/sessions/${sessionId}`, { method: 'DELETE' });
}

export async function stopChat(sessionId) {
  if (!sessionId) return { stopped: false };
  const res = await fetch(`/chat/${sessionId}/stop`, {
    method: 'POST',
    headers: { 'X-Agens-Action': 'stop' }
  });
  if (!res.ok) return { stopped: false };
  return res.json();
}

export async function shutdownAssistant(options = {}) {
  const res = await fetch('/shutdown', {
    method: 'POST',
    headers: { 'X-Agens-Action': 'shutdown' },
    ...options
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, data };
}

export async function getSetupStatus() {
  const res = await fetch('/setup/status');
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to fetch setup status');
  }
  return res.json();
}

export async function fetchModels() {
  const res = await fetch('/api/models');
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to fetch models');
  }
  return res.json();
}

/**
 * @typedef {Object} DoneEventPayload
 * @property {"done"} type
 * @property {string} session_id
 * @property {any} usage
 * @property {any[]} tool_history
 * @property {"await_confirmation"|null} [next_action]
 */

export function streamChat(sessionId, message, model, toolGroups, callbacks) {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message, model, tool_groups: toolGroups }),
        signal: controller.signal
      });

      if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: `HTTP ${res.status}: ${res.statusText}` }));
        callbacks.onError(error.detail || `HTTP ${res.status}: ${res.statusText}`);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let shouldClose = false;

      outer: while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data:')) continue;

          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr) continue;

          let event;
          try {
            event = JSON.parse(jsonStr);
          } catch {
            continue;
          }

          switch (event.type) {
            case 'session':
              if (callbacks.onSession) callbacks.onSession(event.session_id);
              break;
            case 'token':
              callbacks.onToken(event.content);
              break;
            case 'status':
              if (callbacks.onStatus) callbacks.onStatus(event.message);
              break;
            case 'confirmation_required':
              // Forward confirmation requests to the UI handler.
              if (callbacks.onConfirmationRequired) callbacks.onConfirmationRequired(event);
              break;
            case 'confirmation_result':
              // Forward confirmation results to the UI handler.
              if (callbacks.onConfirmationResult) callbacks.onConfirmationResult(event);
              break;

            case 'tool_start':
              callbacks.onToolStart(event.tool, event.arguments);
              break;
            case 'tool_end':
              callbacks.onToolEnd(event.tool, event.result, event.error);
              break;
            case 'done':
              if (callbacks.onDone) callbacks.onDone(event);
              shouldClose = true;
              break;
            case 'error':
              callbacks.onError(event.error);
              shouldClose = true;
              break;
          }

          if (shouldClose) {
            try {
              await reader.cancel();
            } catch {
              // Ignore cancellation errors once the stream is complete.
            }
            break outer;
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        callbacks.onError(err.message);
      }
    }
  })();

  return {
    abort: (reason) => {
      if (reason === 'user_stop') {
        controller.abort();
      } else {
        console.warn('Ignored premature abort call without explicit user reason.');
      }
    }
  };
}

// --- API Keys Endpoints ---

export async function getApiKeys(params = {}) {
  const searchParams = new URLSearchParams();
  if (params.provider) searchParams.append('provider', params.provider);
  if (params.status) searchParams.append('status', params.status);
  if (params.limit !== undefined) searchParams.append('limit', params.limit);
  if (params.offset !== undefined) searchParams.append('offset', params.offset);
  const query = searchParams.toString();

  const res = await fetch(`/api-keys${query ? `?${query}` : ''}`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to fetch API keys');
  }
  return res.json();
}

export async function getApiKey(keyId) {
  const res = await fetch(`/api-keys/${keyId}`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to fetch API key');
  }
  return res.json();
}

export async function createApiKey(data) {
  const res = await fetch('/api-keys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to create API key');
  }
  return res.json();
}

export async function updateApiKeyStatus(keyId, status) {
  const res = await fetch(`/api-keys/${keyId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status })
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to update API key status');
  }
  return res.json();
}

export async function deleteApiKey(keyId) {
  const res = await fetch(`/api-keys/${keyId}`, {
    method: 'DELETE'
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to delete API key');
  }
}



// --- Settings Endpoints ---

export async function getSettings() {
  const res = await fetch('/settings/');
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to fetch settings');
  }
  return res.json();
}

export async function updateSettings(settingsPatch) {
  const res = await fetch('/settings/', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settingsPatch)
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to update settings');
  }
  return res.json();
}
