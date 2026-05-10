<script>
  import ModelSelector from './ModelSelector.svelte';

  // Allow external control of stop button visibility while disabled.
  let { disabled = false, showStop = false, selectedModel = $bindable('gemini/gemini-2.5-flash-lite'), onsubmit, onstop } = $props();

  let text = $state('');
  let textareaRef = $state();

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && text.trim()) {
        if (onsubmit) onsubmit({ text: text.trim(), model: selectedModel });
        text = '';
        if (textareaRef) {
          textareaRef.style.height = 'auto';
        }
      }
    }
  }

  function handleInput() {
    if (textareaRef) {
      textareaRef.style.height = 'auto';
      textareaRef.style.height = Math.min(textareaRef.scrollHeight, 150) + 'px';
    }
  }

  function handleSubmit() {
    if (!disabled && text.trim()) {
      if (onsubmit) onsubmit({ text: text.trim(), model: selectedModel });
      text = '';
      if (textareaRef) {
        textareaRef.style.height = 'auto';
      }
    }
  }

  function handleStop() {
    if (onstop) onstop();
  }

  function handleModelChange(val) {
    selectedModel = val;
  }
</script>

<div class="input-container">
  <div class="wrapper" class:disabled>
    <textarea
      bind:this={textareaRef}
      bind:value={text}
      oninput={handleInput}
      onkeydown={handleKeydown}
      placeholder="Ask anything about your architecture..."
      rows="1"
      {disabled}
    ></textarea>
    
    <div class="bottom-bar">
      <ModelSelector
        bind:selectedModel
        onchange={handleModelChange}
      />

      <div class="actions">
        {#if showStop}
          <button class="stop-btn" onclick={handleStop}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="6" y="6" width="12" height="12" rx="2" ry="2"/>
            </svg>
            Stop
          </button>
        {:else}
          <button class="send-btn" aria-label="Send message" onclick={handleSubmit} class:active={text.trim()} disabled={disabled}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <line x1="12" y1="19" x2="12" y2="5"/>
              <polyline points="5 12 12 5 19 12"/>
            </svg>
          </button>
        {/if}
      </div>
    </div>
  </div>
  
  <p class="disclaimer">
    The Intelligence Layer may provide inaccurate information. Verify critical outputs.
  </p>
</div>

<style>
  .input-container {
    width: 100%;
    margin-top: 16px;
    font-family: 'Inter', sans-serif;
  }

  .wrapper {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 0;
    padding: 8px 14px 10px;
    background: var(--bg-input);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border-radius: 12px;
    border: 0.5px solid var(--border-main);
    box-shadow: var(--shadow-input);
    transition: all 0.3s ease;
  }

  .wrapper.disabled {
    background: var(--surface-container-high);
    border-color: var(--border-main);
    opacity: 0.8;
  }

  textarea {
    flex: 1;
    background: transparent;
    border: none;
    color: var(--text-primary);
    font-size: 16px;
    line-height: 1.5;
    padding: 10px 4px 6px;
    resize: none;
    min-height: 48px;
    max-height: 150px;
    outline: none;
    font-family: inherit;
    width: 100%;
  }

  textarea::placeholder {
    color: var(--text-placeholder);
  }

  textarea:disabled {
    color: var(--text-tertiary);
    pointer-events: none;
  }

  /* Hide scrollbar */
  textarea::-webkit-scrollbar {
    display: none;
  }
  textarea {
    -ms-overflow-style: none;
    scrollbar-width: none;
  }

  /* Bottom row: model selector + actions */
  .bottom-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-top: 4px;
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .send-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    border: none;
    background: var(--accent-primary);
    color: var(--bg-surface);
    box-shadow: 0 4px 14px var(--glow-bg);
    cursor: pointer;
    transition: all 0.2s ease;
    opacity: 0.5;
  }

  .send-btn.active {
    opacity: 1;
  }

  .send-btn.active:hover {
    transform: scale(1.05);
  }

  .send-btn.active:active {
    transform: scale(0.95);
  }

  /* Dim send button when input is locked. */
  .send-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }

  .stop-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(127, 39, 55, 0.2);
    color: var(--error-dim);
    border: 1px solid rgba(127, 39, 55, 0.3);
    padding: 6px 16px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
  }

  .stop-btn:hover {
    background: rgba(127, 39, 55, 0.4);
  }

  .disclaimer {
    text-align: center;
    font-size: 10px;
    color: var(--text-disclaimer);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    font-weight: 500;
    margin-top: 12px;
  }
</style>
