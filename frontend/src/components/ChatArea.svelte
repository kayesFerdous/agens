<script>
  import {
    messages,
    isStreaming,
    activeSessionId,
    restoredConfirmation,
    toolGroups,
  } from "../lib/store.js";
  import { streamChat, authorizeSudo, stopChat } from "../lib/api.js";
  import { sessionService } from "../lib/sessionService.svelte.js";

  import WelcomeScreen from "./WelcomeScreen.svelte";
  import Message from "./Message.svelte";
  import ChatInput from "./ChatInput.svelte";

  let currentStream = $state(null);
  let streamSessionId = $state(null);
  let chatWindow;
  // Track pending dangerous command confirmations locally.
  let pendingConfirmation = $state(null);
  // Keep the latest confirmation payload for immediate display and done-state reconciliation.
  let confirmationRequest = $state(null);
  // Prevent duplicate confirmation submissions.
  let confirmationBusy = $state(false);
  // Track sudo secret modal flow state for privileged commands.
  let sudoAuthPending = $state(null);
  let sudoAuthRequest = $state(null);
  let sudoSecretInput = $state("");
  let sudoAuthLoading = $state(false);
  let sudoAuthError = $state(null);
  let sudoAuthSuccess = $state(false);
  // Keep a ref for autofocus when the modal opens.
  let sudoInputRef = $state();

  // Keep the view pinned to the latest content in runes mode.
  $effect(() => {
    // Access $messages to establish a reactive dependency so it scrolls on updates
    if (chatWindow && $messages) {
      chatWindow.scrollTop = chatWindow.scrollHeight;
    }
  });

  // Bug 1 fix: Pull restored confirmation data from the session loader.
  $effect(() => {
    if ($restoredConfirmation) {
      pendingConfirmation = $restoredConfirmation;
      restoredConfirmation.set(null); // clear after consuming
    }
  });

  // Focus the secret input whenever sudo authorization is requested.
  $effect(() => {
    if (sudoAuthPending && sudoInputRef) {
      sudoInputRef.focus();
    }
  });

  function finalizeStream() {
    currentStream = null;
    streamSessionId = null;
    isStreaming.set(false);
  }

  async function abortStream() {
    const sessionId = streamSessionId || $activeSessionId;
    if (sessionId) {
      try {
        await stopChat(sessionId);
      } catch (err) {
        console.error("Failed to stop stream:", err);
      }
    }

    if (currentStream) {
      currentStream.abort("user_stop");
      currentStream = null;
    }
    streamSessionId = null;
    isStreaming.set(false);
    messages.update((m) => {
      const last = [...m].reverse().find((x) => x.role === "assistant");
      if (last) {
        last.isThinking = false;
        if (!last.content.trim()) {
          last.content = "_Stopped._";
        } else if (!last.content.includes("_Stopped._")) {
          last.content += "\n\n_Stopped._";
        }
      }
      return m;
    });
  }

  function generateId() {
    return Math.random().toString(36).substr(2, 9);
  }

  function handleSuggest(text) {
    handleSubmit(text);
  }

  // Default model — kept in sync with ModelSelector default
  const DEFAULT_MODEL = "gemini/gemini-2.5-flash-lite";
  const KEY_UNAVAILABLE_PREFIX = "All API keys are currently exhausted or unavailable.";

  function handleSubmit(textOrPayload) {
    let text, model;
    if (typeof textOrPayload === "string") {
      // Called from WelcomeScreen suggestion chips
      text = textOrPayload;
      model = DEFAULT_MODEL;
    } else if (textOrPayload && typeof textOrPayload === "object") {
      // Called from ChatInput with { text, model }
      text = textOrPayload.text;
      model = textOrPayload.model ?? DEFAULT_MODEL;
    } else {
      return;
    }
    if (!text || $isStreaming || currentStream) return;

    confirmationRequest = null;
    sudoAuthRequest = null;
    pendingConfirmation = null;
    sudoAuthPending = null;
    confirmationBusy = false;
    sudoAuthError = null;
    sudoAuthSuccess = false;

    const sessionId = $activeSessionId;

    // Add user msg
    messages.update((m) => [
      ...m,
      {
        id: generateId(),
        role: "user",
        content: text,
        toolBlocks: [],
        isThinking: false,
      },
    ]);

    // Add assistant msg skeleton
    const assistantId = generateId();
    messages.update((m) => [
      ...m,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        toolBlocks: [],
        isThinking: true,
      },
    ]);

    isStreaming.set(true);

    currentStream = streamChat(sessionId, text, model, $toolGroups, {
      async onSession(id) {
        streamSessionId = id;
      },
      onToken(content) {
        messages.update((m) => {
          const am = m.find((x) => x.id === assistantId);
          if (am) {
            am.content += content;
            am.isThinking = false;
          }
          return m;
        });
      },
      onStatus(msg) {
        messages.update((m) => {
          // Insert the status message right before the active assistant message skeleton
          const aiIndex = m.findIndex((x) => x.id === assistantId);
          const statusId = generateId();
          if (aiIndex !== -1) {
            m.splice(aiIndex, 0, {
              id: statusId,
              role: "status",
              content: msg,
            });
          } else {
            // Fallback if AI message isn't found for some reason
            m.push({
              id: statusId,
              role: "status",
              content: msg,
            });
          }
          return [...m];
        });
      },
      onToolStart(tool, args) {
        messages.update((m) => {
          const am = m.find((x) => x.id === assistantId);
          if (am) {
            am.toolBlocks.push({
              tool,
              arguments: args,
              result: null,
              error: null,
              status: "running",
            });
            am.isThinking = false;
          }
          return m;
        });
      },
      onToolEnd(tool, result, error) {
        messages.update((m) => {
          const am = m.find((x) => x.id === assistantId);
          if (am) {
            // find last running block for this tool
            const blocks = am.toolBlocks;
            for (let i = blocks.length - 1; i >= 0; i--) {
              if (blocks[i].tool === tool && blocks[i].status === "running") {
                blocks[i].result = result;
                blocks[i].error = error;
                blocks[i].status = error ? "error" : "done";
                break;
              }
            }
          }
          return m;
        });
      },
      onConfirmationRequired(event) {
        confirmationRequest = {
          reason: event.reason,
          preview: event.preview,
          requires_sudo_auth: event.requires_sudo_auth ?? false,
        };
        pendingConfirmation = confirmationRequest;
        confirmationBusy = false;
      },
      onSudoAuthRequired(event) {
        // Cache sudo auth payload for the done event.
        sudoAuthRequest = { preview: event.preview };
      },
      onConfirmationResult(event) {
        // Clear any pending confirmation or sudo auth state when a result arrives.
        pendingConfirmation = null;
        sudoAuthPending = null;
        sudoAuthLoading = false;
        sudoAuthError = null;
        sudoAuthSuccess = false;
        confirmationBusy = false;
        if (event.message) {
          messages.update((m) => [
            ...m,
            { id: generateId(), role: "status", content: event.message },
          ]);
        }
        if (event.error) {
          messages.update((m) => [
            ...m,
            {
              id: generateId(),
              role: "assistant",
              content: `\n\n> **Error:** ${event.error}`,
              toolBlocks: [],
              isThinking: false,
            },
          ]);
        }
        if (event.result) {
          messages.update((m) => {
            const am = m.find((x) => x.id === assistantId);
            if (am) {
              const blocks = am.toolBlocks;
              let applied = false;
              for (let i = blocks.length - 1; i >= 0; i--) {
                if (
                  blocks[i].tool === event.tool &&
                  blocks[i].status === "running"
                ) {
                  blocks[i].result = event.result;
                  blocks[i].error = event.error;
                  blocks[i].status = event.error ? "error" : "done";
                  applied = true;
                  break;
                }
              }
              if (!applied) {
                blocks.push({
                  tool: event.tool,
                  arguments: null,
                  result: event.result,
                  error: event.error,
                  status: event.error ? "error" : "done",
                });
              }
            }
            return m;
          });
        }
      },
      async onDone(event) {
        const sessionId = event?.session_id;
        const shouldRefreshSessions = sessionId && sessionId !== $activeSessionId;
        finalizeStream();

        const nextAction = event?.next_action ?? null;
        if (nextAction === "await_confirmation") {
          pendingConfirmation = confirmationRequest || null;
          confirmationBusy = false;
          sudoAuthPending = null;
          sudoAuthRequest = null;
          sudoAuthError = null;
          sudoAuthSuccess = false;
        } else if (nextAction === "await_sudo_auth") {
          pendingConfirmation = null;
          confirmationBusy = false;
          sudoAuthPending = sudoAuthRequest || null;
          sudoSecretInput = "";
          sudoAuthLoading = false;
          sudoAuthError = null;
          sudoAuthSuccess = false;
        } else {
          pendingConfirmation = null;
          sudoAuthPending = null;
          confirmationBusy = false;
          sudoAuthLoading = false;
          sudoAuthError = null;
          sudoAuthSuccess = false;
        }

        confirmationRequest = null;
        sudoAuthRequest = null;

        if (shouldRefreshSessions) {
          activeSessionId.set(sessionId);
          try {
            await sessionService.refresh();
          } catch (err) {
            console.error("Failed to refresh sessions:", err);
          }
        }
      },
      onError(err) {
        finalizeStream();
        confirmationRequest = null;
        sudoAuthRequest = null;
        pendingConfirmation = null;
        sudoAuthPending = null;
        confirmationBusy = false;
        sudoAuthLoading = false;
        sudoAuthError = null;
        sudoAuthSuccess = false;
        messages.update((m) => {
          const am = m.find((x) => x.id === assistantId);
          if (am) {
            if (String(err).startsWith(KEY_UNAVAILABLE_PREFIX)) {
              am.content = err;
            } else {
              am.content += `\n\n> **Error:** ${err}`;
            }
            am.isThinking = false;
          }
          return m;
        });
      },
    });
  }

  function handleStop() {
    void abortStream();
  }

  function handleConfirmation(choice) {
    if (confirmationBusy) return;

    // Bug 2 fix: Frontend-first sudo secret collection.
    // If user clicked YES and it needs sudo, show the secret modal immediately.
    // Do NOT send the confirmation message to the backend yet.
    if (
      choice === "YES" &&
      pendingConfirmation &&
      pendingConfirmation.requires_sudo_auth
    ) {
      sudoAuthPending = pendingConfirmation;
      sudoSecretInput = "";
      sudoAuthLoading = false;
      sudoAuthError = null;
      sudoAuthSuccess = false;
      return;
    }

    // Otherwise, normal confirmation flow (or Cancel).
    confirmationBusy = true;
    pendingConfirmation = null;
    handleSubmit(choice);
  }

  async function handleSudoAuth() {
    // Authorize sudo with the secret before sending the second YES.
    if (sudoAuthLoading || !sudoSecretInput.trim()) return;
    sudoAuthLoading = true;
    sudoAuthError = null;
    try {
      const sessionId = $activeSessionId;
      const res = await authorizeSudo(sessionId, sudoSecretInput.trim());
      if (res.ok) {
        sudoAuthSuccess = true;
        sudoSecretInput = "";
        sudoAuthPending = null;
        await handleSubmit("YES");
      } else {
        sudoAuthError = res.data?.detail ?? "Authorization failed. Try again.";
      }
    } catch {
      sudoAuthError = "Network error. Please try again.";
    } finally {
      sudoAuthLoading = false;
      sudoAuthSuccess = false;
    }
  }

  function cancelSudoAuth() {
    // Close the modal and optionally cancel the pending action.
    sudoAuthPending = null;
    sudoSecretInput = "";
    sudoAuthError = null;
    sudoAuthLoading = false;
    sudoAuthSuccess = false;
    handleSubmit("No");
  }

  function handleSudoKeydown(e) {
    // Allow Enter to submit the secret without using the chat input.
    if (e.key === "Enter") {
      e.preventDefault();
      handleSudoAuth();
    }
  }

  function handleSudoBackdrop() {
    // Only allow closing the modal when not authorizing.
    if (!sudoAuthLoading) cancelSudoAuth();
  }
</script>

<div class="chat-container">
  <div class="scroll-area" bind:this={chatWindow}>
    <div class="content">
      {#if $messages.length === 0}
        <div class="welcome-wrapper">
          <WelcomeScreen onsuggest={handleSuggest} />
        </div>
      {:else}
        <div class="message-list">
          {#each $messages as message, i (message.id)}
            <Message
              {message}
              isLive={$isStreaming && i === $messages.length - 1}
            />
          {/each}
        </div>
        {#if pendingConfirmation}
          <!-- Render the inline confirmation card under the latest assistant message. -->
          <div class="confirmation-card" role="alert">
            <div class="confirmation-header">
              <span class="warning-icon" aria-hidden="true"></span>
              <span class="confirmation-title">Confirm command</span>
            </div>
            <code class="confirm-code">{pendingConfirmation.preview}</code>
            <p class="confirm-reason">{pendingConfirmation.reason}</p>
            {#if pendingConfirmation.requires_sudo_auth}
              <!-- Warn that a secret will be required after confirming. -->
              <p class="confirm-sudo-note">
                This command requires elevated privileges. After confirming,
                enter your agent secret.
              </p>
            {/if}
            <div class="confirm-actions">
              <button
                class="confirm-yes"
                onclick={() => handleConfirmation("YES")}
                disabled={confirmationBusy}
              >
                Yes, run it
              </button>
              <button
                class="confirm-cancel"
                onclick={() => handleConfirmation("No")}
                disabled={confirmationBusy}
              >
                Cancel
              </button>
            </div>
          </div>
        {/if}
        <div class="scroll-spacer"></div>
      {/if}
    </div>
  </div>

  <div class="input-zone">
    <div class="input-wrapper">
      <ChatInput
        disabled={$isStreaming || !!pendingConfirmation || !!sudoAuthPending}
        showStop={$isStreaming}
        onsubmit={handleSubmit}
        onstop={handleStop}
      />
    </div>
    {#if pendingConfirmation || sudoAuthPending}
      <!-- Hint is only visible when authorization is in progress. -->
      <p class="confirm-hint">Complete the authorization above to continue</p>
    {/if}
  </div>

  {#if sudoAuthPending}
    <!-- Modal overlay for sudo secret authorization. -->
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <div class="sudo-modal-overlay" role="presentation" onclick={handleSudoBackdrop}>
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <div class="sudo-modal" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()}>
        <div class="sudo-modal-header">
          <div class="sudo-modal-icon" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <rect x="4" y="11" width="16" height="10" rx="2"></rect>
              <path d="M8 11V7a4 4 0 0 1 8 0v4"></path>
            </svg>
          </div>
          <div>
            <h2 class="sudo-modal-title">Authorize sudo command</h2>
            <p class="sudo-modal-subtitle">
              Enter your agent secret to authorize this command. This is not
              your system password.
            </p>
          </div>
        </div>
        <code class="sudo-code">{sudoAuthPending.preview}</code>
        <input
          class="sudo-input"
          type="password"
          bind:this={sudoInputRef}
          bind:value={sudoSecretInput}
          onkeydown={handleSudoKeydown}
          placeholder="Agent secret"
          disabled={sudoAuthLoading}
        />
        {#if sudoAuthError}
          <p class="sudo-error">{sudoAuthError}</p>
        {/if}
        <div class="sudo-actions">
          <button
            class="sudo-btn-primary"
            onclick={handleSudoAuth}
            disabled={sudoAuthLoading || !sudoSecretInput.trim()}
          >
            {#if sudoAuthLoading}
              Authorizing...
            {:else if sudoAuthSuccess}
              Authorized
            {:else}
              Authorize
            {/if}
          </button>
          <button
            class="sudo-btn-ghost"
            onclick={cancelSudoAuth}
            disabled={sudoAuthLoading}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .chat-container {
    width: 100%;
    height: 100%;
    position: relative;
    overflow: hidden;
  }

  .scroll-area {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-width: none;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .scroll-area::-webkit-scrollbar {
    display: none;
  }

  .content {
    flex: 1;
    width: 100%;
    max-width: 880px;
    display: flex;
    flex-direction: column;
    padding: 32px 16px 0;
  }

  .welcome-wrapper {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .message-list {
    display: flex;
    flex-direction: column;
    gap: 32px;
    width: 100%;
    padding-bottom: 24px;
  }

  .scroll-spacer {
    height: 190px;
    flex-shrink: 0;
    width: 100%;
  }

  .input-zone {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding-bottom: 16px;
    padding-top: 24px;
    pointer-events: none;
    background: linear-gradient(to top, var(--ag-cream) 68%, rgba(245,240,232,0));
    z-index: 10;
  }

  .input-wrapper {
    width: 100%;
    max-width: 880px;
    padding: 0 16px;
    pointer-events: auto;
  }

  /* Confirmation card and hint styles. */
  .confirmation-card {
    margin-top: 16px;
    padding: 16px 18px;
    border-radius: 18px;
    border: 0.5px solid rgba(201,124,74,0.25);
    background: var(--ag-warm-light);
    color: var(--ag-ink);
    display: flex;
    flex-direction: column;
    gap: 12px;
    box-shadow: none;
  }

  .confirmation-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 500;
  }

  .warning-icon {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--ag-warm);
  }

  .confirmation-title {
    font-size: 14px;
    letter-spacing: 0;
  }

  .confirm-code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
      "Liberation Mono", "Courier New", monospace;
    background: var(--ag-warm-white);
    color: var(--ag-ink-2);
    border: 0.5px solid var(--ag-border);
    padding: 10px 12px;
    border-radius: 8px;
    display: block;
    white-space: pre-wrap;
  }

  .confirm-reason {
    margin: 0;
    color: var(--ag-ink-2);
    font-size: 13px;
    line-height: 1.5;
  }

  .confirm-sudo-note {
    margin: 0;
    color: var(--ag-warm);
    font-size: 12px;
    line-height: 1.4;
  }

  .confirm-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }

  .confirm-yes {
    background: var(--ag-warm-light);
    color: var(--ag-warm);
    border: 0.5px solid rgba(201,124,74,0.25);
    padding: 8px 14px;
    border-radius: 12px;
    font-weight: 500;
    cursor: pointer;
  }

  .confirm-yes:disabled,
  .confirm-cancel:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .confirm-cancel {
    background: transparent;
    color: var(--ag-ink);
    border: 0.5px solid var(--ag-border);
    padding: 8px 14px;
    border-radius: 12px;
    font-weight: 500;
    cursor: pointer;
  }

  .confirm-hint {
    margin: 8px 0 0;
    font-size: 11px;
    color: var(--ag-ink-3);
    text-align: center;
    letter-spacing: 0.01em;
  }

  /* Sudo authorization modal styles. */
  .sudo-modal-overlay {
    position: fixed;
    inset: 0;
    z-index: 2000;
    background: rgba(28, 24, 20, 0.42);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }

  .sudo-modal {
    width: 100%;
    max-width: 520px;
    background: var(--ag-warm-white);
    border: 0.5px solid var(--ag-border);
    border-radius: 24px;
    padding: 24px;
    box-shadow: none;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .sudo-modal-header {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }

  .sudo-modal-icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: var(--ag-warm-light);
    color: var(--ag-warm);
    border: 0.5px solid rgba(201,124,74,0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
  }

  .sudo-modal-title {
    margin: 0;
    font-size: 18px;
    font-weight: 500;
    color: var(--ag-ink);
  }

  .sudo-modal-subtitle {
    margin: 4px 0 0;
    font-size: 13px;
    color: var(--ag-ink-2);
    line-height: 1.5;
  }

  .sudo-code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
      "Liberation Mono", "Courier New", monospace;
    background: var(--ag-warm-white);
    color: var(--ag-ink-2);
    border: 0.5px solid var(--ag-border);
    padding: 10px 12px;
    border-radius: 8px;
    display: block;
    white-space: pre-wrap;
  }

  .sudo-input {
    width: 100%;
    padding: 12px 14px;
    border-radius: 12px;
    border: 0.5px solid var(--ag-border);
    background: var(--ag-warm-white);
    color: var(--ag-ink);
    font-size: 14px;
    font-family: inherit;
  }

  .sudo-input:disabled {
    opacity: 0.7;
  }

  .sudo-error {
    margin: 0;
    font-size: 12px;
    color: var(--ag-warm);
  }

  .sudo-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }

  .sudo-btn-primary {
    padding: 10px 16px;
    border-radius: 12px;
    border: 0.5px solid rgba(201,124,74,0.25);
    background: var(--ag-warm-light);
    color: var(--ag-warm);
    font-weight: 500;
    cursor: pointer;
  }

  .sudo-btn-ghost {
    padding: 10px 16px;
    border-radius: 12px;
    border: 0.5px solid var(--ag-border);
    background: transparent;
    color: var(--ag-ink);
    font-weight: 500;
    cursor: pointer;
  }

  .sudo-btn-primary:disabled,
  .sudo-btn-ghost:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
