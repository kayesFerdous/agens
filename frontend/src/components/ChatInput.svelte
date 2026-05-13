<script>
  import ModelSelector from './ModelSelector.svelte';
  import ToolGroupSelector from './ToolGroupSelector.svelte';

  // Allow external control of stop button visibility while disabled.
  let { disabled = false, showStop = false, selectedModel = $bindable('gemini/gemini-2.5-flash-lite'), onsubmit, onstop } = $props();

  let text = $state('');

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && text.trim()) {
        if (onsubmit) onsubmit({ text: text.trim(), model: selectedModel });
        text = '';
      }
    }
  }

  function handleSubmit() {
    if (!disabled && text.trim()) {
      if (onsubmit) onsubmit({ text: text.trim(), model: selectedModel });
      text = '';
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
    <div class="textarea-grid">
      <textarea
        bind:value={text}
        onkeydown={handleKeydown}
        placeholder="Ask anything about your architecture..."
        rows="1"
        {disabled}
      ></textarea>
      <div class="textarea-sizer" aria-hidden="true">{text + '\u200b'}</div>
    </div>
    
    <div class="bottom-bar">
      <div class="control-group">
        <ModelSelector
          bind:selectedModel
          onchange={handleModelChange}
        />
        <ToolGroupSelector />
      </div>

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
    agens may provide inaccurate information. Verify critical outputs.
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

  .textarea-grid {
    display: grid;
    flex: 1;
    max-height: 250px;
    overflow: hidden;
  }

  .textarea-grid > textarea,
  .textarea-grid > .textarea-sizer {
    grid-area: 1 / 1 / 2 / 2;
    font-size: 14px;
    line-height: 1.5;
    padding: 10px 4px 6px;
    font-family: inherit;
    word-break: break-word;
    min-height: 48px;
  }

  .textarea-sizer {
    white-space: pre-wrap;
    visibility: hidden;
    color: transparent;
    pointer-events: none;
  }

  textarea {
    width: 100%;
    height: 100%;
    background: transparent;
    border: none;
    color: var(--ag-ink);
    resize: none;
    outline: none;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: rgba(123, 110, 170, 0.3) transparent;
  }

  textarea::placeholder {
    color: var(--ag-ink-3);
  }

  textarea:disabled {
    color: var(--ag-ink-3);
    pointer-events: none;
  }

  textarea::-webkit-scrollbar {
    width: 4px;
  }
  textarea::-webkit-scrollbar-track {
    background: transparent;
  }
  textarea::-webkit-scrollbar-thumb {
    background: rgba(123, 110, 170, 0.3);
    border-radius: 4px;
  }

  .bottom-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-top: 4px;
  }

  .control-group {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    flex-wrap: wrap;
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

  @media (max-width: 560px) {
    .bottom-bar {
      align-items: flex-end;
    }

    .control-group {
      gap: 6px;
    }
  }

</style>
