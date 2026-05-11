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
          <button class="stop-btn" type="button" aria-label="Stop response" onclick={handleStop}>
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
    Agens may provide inaccurate information. Verify critical outputs.
  </p>
</div>

<style>

  .input-container {
    width: 100%;
    margin-top: 16px;
    font-family: var(--font-sans);
  }

  .wrapper {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 0;
    padding: 12px 16px;
    background: var(--ag-warm-white);
    border-radius: 24px;
    border: 0.5px solid var(--ag-border);
    transition: all 0.3s ease;
  }

  .wrapper:focus-within {
    border-color: var(--ag-accent);
    box-shadow: 0 0 0 3px var(--ag-accent-glow);
  }

  .wrapper.disabled {
    background: var(--ag-surface);
    opacity: 0.8;
  }

  textarea {
    flex: 1;
    background: transparent;
    border: none;
    color: var(--ag-ink);
    font-size: 14px;
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
    color: var(--ag-ink-3);
  }

  textarea:disabled {
    color: var(--ag-ink-3);
    pointer-events: none;
  }

  textarea::-webkit-scrollbar {
    display: none;
  }
  textarea {
    -ms-overflow-style: none;
    scrollbar-width: none;
  }

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
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    border: none;
    background: var(--ag-ink);
    color: var(--ag-cream);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .send-btn:hover {
    background: var(--ag-ink-2);
  }
  .send-btn:active {
    transform: scale(0.95);
  }

  .send-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    background: var(--ag-ink-3);
  }

  .stop-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--ag-warm-light);
    color: var(--ag-warm);
    border: 0.5px solid rgba(201,124,74,0.25);
    padding: 6px 16px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s;
  }

  .stop-btn:hover {
    background: var(--ag-surface);
  }

  .disclaimer {
    text-align: center;
    font-size: 10px;
    color: var(--ag-ink-3);
    letter-spacing: 0.01em;
    font-weight: 500;
    margin-top: 12px;
  }

</style>
