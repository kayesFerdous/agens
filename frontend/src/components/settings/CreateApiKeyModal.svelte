<script>
  import { createApiKey } from "../../lib/api.js";

  export let onClose = () => {};
  export let onSuccess = () => {};

  let provider = "gemini";
  let apiKey = "";
  let label = "";
  let loading = false;
  let error = null;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!apiKey.trim()) {
      error = "API key is required";
      return;
    }

    loading = true;
    error = null;
    try {
      await createApiKey({
        provider,
        api_key: apiKey.trim(),
        label: label.trim() || undefined,
      });
      onSuccess();
    } catch (err) {
      error = err.message || "Failed to create API key";
    } finally {
      loading = false;
    }
  }

  // Handle escape key
  function handleKeydown(e) {
    if (e.key === "Escape") onClose();
  }

  if (typeof window !== "undefined") {
    window.addEventListener("keydown", handleKeydown);
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay" onclick={onClose}>
  <div class="modal-content" onclick={(e) => e.stopPropagation()}>
    <div class="modal-header">
      <div class="modal-icon">
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
        </svg>
      </div>
      <div>
        <h2 class="modal-title">Add API Key</h2>
        <p class="modal-subtitle">
          Connect a new provider to power the intelligence layer.
        </p>
      </div>
    </div>

    {#if error}
      <div class="error-msg">
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        {error}
      </div>
    {/if}

    <form onsubmit={handleSubmit} class="api-form">
      <div class="form-group">
        <label for="provider">Provider</label>
        <select id="provider" bind:value={provider} disabled={loading}>
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic</option>
          <option value="deepseek">DeepSeek</option>
          <option value="gemini">Gemini</option>
        </select>
      </div>

      <div class="form-group">
        <label for="label">Label (Optional)</label>
        <input
          id="label"
          type="text"
          bind:value={label}
          placeholder="e.g. My Production Key"
          disabled={loading}
        />
        <span class="hint"
          >A recognizable name to help you identify this key later.</span
        >
      </div>

      <div class="form-group">
        <label for="apiKey">API Key</label>
        <input
          id="apiKey"
          type="password"
          bind:value={apiKey}
          placeholder="Paste your secret key here..."
          disabled={loading}
          required
        />
        <span class="hint"
          >Your key will be securely encrypted before it is stored.</span
        >
      </div>

      <div class="modal-actions">
        <button
          type="button"
          class="btn-cancel"
          onclick={onClose}
          disabled={loading}>Cancel</button
        >

        <button
          type="submit"
          class="btn-submit"
          disabled={loading || !apiKey.trim()}
        >
          {#if loading}
            <div class="spinner-small"></div>
            Saving...
          {:else}
            Save Key
          {/if}
        </button>
      </div>
    </form>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    z-index: 1000;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    animation: fadeIn 0.2s ease-out;
  }

  .modal-content {
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 16px;
    padding: 32px;
    width: 100%;
    max-width: 480px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .modal-header {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 24px;
  }

  .modal-icon {
    width: 48px;
    height: 48px;
    flex-shrink: 0;
    border-radius: 12px;
    background: var(--glow-bg);
    color: var(--accent-primary);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .modal-title {
    margin: 0 0 4px;
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.01em;
  }

  .modal-subtitle {
    margin: 0;
    font-size: 14px;
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .error-msg {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px;
    margin-bottom: 24px;
    background: var(--badge-err-bg);
    border: 1px solid var(--badge-err-border);
    border-radius: 8px;
    color: var(--status-err);
    font-size: 14px;
    font-weight: 500;
  }

  .api-form {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  label {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
  }

  input,
  select {
    width: 100%;
    padding: 12px 16px;
    background: var(--bg-input);
    border: 1px solid var(--border-main);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 14px;
    font-family: inherit;
    transition:
      border-color 0.2s,
      box-shadow 0.2s;
  }

  input:focus,
  select:focus {
    outline: none;
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 2px rgba(217, 119, 87, 0.2);
  }

  input:disabled,
  select:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  input::placeholder {
    color: var(--text-placeholder);
  }

  .hint {
    font-size: 12px;
    color: var(--text-tertiary);
  }

  .modal-actions {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    margin-top: 12px;
  }

  .btn-cancel {
    padding: 10px 16px;
    border-radius: 8px;
    border: 1px solid var(--border-main);
    background: transparent;
    color: var(--text-primary);
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-cancel:hover:not(:disabled) {
    background: var(--surface-container-high);
  }

  .btn-submit {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    border-radius: 8px;
    border: none;
    background: var(--accent-primary);
    color: var(--bg-surface);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-submit:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .btn-submit:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .spinner-small {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(16px) scale(0.96);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
</style>
