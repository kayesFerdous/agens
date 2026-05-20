<script>
  export let tool = '';
  export let arguments_obj = {};
  export let result = null;
  export let error = null;
  export let status = 'running'; // 'running', 'done', 'error'

  let expanded = false;

  function toggleExpanded() {
    if (arguments_obj || result || error) {
      expanded = !expanded;
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="trace" data-state={status} data-expand={String(!!(arguments_obj || result || error))} data-open={String(expanded)} on:click={toggleExpanded}>
  <div class="trace-row">
    <div class="trace-left">
      {#if status === 'running'}
        <div class="ind run"></div>
      {:else if status === 'error'}
        <div class="ind err"></div>
      {:else}
        <div class="ind ok"></div>
      {/if}
      <span class="t-name">{tool}</span>
    </div>
    <div class="trace-right">
      {#if status === 'error'}
        <span class="t-meta err-text">error</span>
      {:else if status === 'done' && result && typeof result === 'string'}
        <span class="t-meta">{result.length > 20 ? result.slice(0, 15) + '...' : result}</span>
      {:else if status === 'done' && result}
        <span class="t-meta">done</span>
      {/if}
      
      {#if arguments_obj || result || error}
        <span class="t-chev">›</span>
      {/if}
    </div>
  </div>
  
  <div class="sheet">
    <div class="sheet-scroll">
      <div class="sheet-inner">
        <div class="out-section">
          {#if arguments_obj && Object.keys(arguments_obj).length > 0}
            <div class="section-label">Input</div>
            {#each Object.entries(arguments_obj) as [k, v]}
              <div class="out-kv">
                <span class="j-key">"{k}"</span><span class="j-punc">:</span>
                <span class="v pre input-val">{typeof v === 'object' ? JSON.stringify(v, null, 2) : v}</span>
              </div>
            {/each}
          {/if}

          {#if result || error}
            {#if arguments_obj && Object.keys(arguments_obj).length > 0}
              <div class="divider"></div>
            {/if}
            <div class="section-label">Output</div>
            
            {#if error}
              <div class="out-kv">
                <span class="err-line pre">{typeof error === 'object' ? JSON.stringify(error, null, 2) : String(error)}</span>
              </div>
            {:else if typeof result === 'object' && result !== null}
              {#each Object.entries(result).slice(0, 5) as [k, v]}
                <div class="out-kv">
                  <span class="j-key">"{k}"</span><span class="j-punc">:</span>
                  <span class="v pre">{typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v)}</span>
                </div>
              {/each}
              {#if Object.keys(result).length > 5}
                <div class="out-kv"><span class="j-punc">...</span></div>
              {/if}
            {:else}
              <div class="out-kv">
                <span class="v pre">{String(result)}</span>
              </div>
            {/if}
          {/if}
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .trace {
    display: flex;
    flex-direction: column;
    max-width: 480px;
    cursor: pointer;
    opacity: 0;
    transform: translateY(1px);
    animation: traceIn 0.2s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    position: relative;
    font-family: var(--font-sans);
  }

  .trace-row {
    display: flex;
    align-items: center;
    height: 22px;
    gap: 10px;
    padding: 3px 0;
    border-top: 1px solid var(--ag-border);
    transition: border-color 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .trace:hover .trace-row {
    border-top-color: var(--ag-ink-3);
  }

  .trace[data-state="error"] .trace-row {
    border-top-color: var(--ag-warm-light);
  }

  .trace-left {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
    min-width: 0;
  }

  .trace-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  .ind {
    width: 5px;
    height: 5px;
    flex-shrink: 0;
    position: relative;
  }

  /* running: sliding bar */
  .ind.run {
    width: 10px;
    height: 2px;
    border-radius: 1px;
    background: var(--ag-accent);
    animation: slide 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  }
  @keyframes slide {
    0%, 100% { transform: translateX(-3px); opacity: 0.4; }
    50% { transform: translateX(3px); opacity: 1; }
  }

  /* success: solid dot */
  .ind.ok {
    background: var(--ag-accent);
    border-radius: 50%;
    opacity: 0.7;
    animation: dotIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
  @keyframes dotIn {
    from { transform: scale(0); opacity: 0; }
    to { transform: scale(1); opacity: 0.7; }
  }

  /* error: small rotated square */
  .ind.err {
    background: var(--ag-warm);
    border-radius: 0.5px;
    transform: rotate(45deg);
    opacity: 0.6;
    width: 4px;
    height: 4px;
  }

  .t-name {
    font-size: 11px;
    font-weight: 500;
    color: var(--ag-ink);
    letter-spacing: -0.01em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .t-meta {
    font-size: 11px;
    font-weight: 400;
    color: var(--ag-ink-3);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  
  .t-meta.err-text {
    color: var(--ag-warm);
  }

  .t-chev {
    font-size: 13px;
    color: var(--ag-ink-3);
    opacity: 0;
    transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.2s;
    transform: rotate(0deg);
    margin-left: 2px;
  }
  .trace[data-expand="true"] .t-chev { opacity: 0.5; }
  .trace[data-open="true"] .t-chev { transform: rotate(90deg); opacity: 0.8; }

  /* Sheet */
  .sheet {
    max-height: 0;
    overflow: hidden;
    opacity: 0;
    transition: max-height 0.25s cubic-bezier(0.4, 0, 0.2, 1),
                opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1),
                padding 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    padding: 0 0 0 15px;
    position: relative;
    background: transparent;
  }
  .trace[data-open="true"] .sheet {
    max-height: 414px; /* 400px + 6px + 8px padding */
    opacity: 1;
    padding: 6px 0 8px 15px;
  }

  .sheet-scroll {
    max-height: 400px;
    overflow-y: auto;
  }

  .sheet-scroll::-webkit-scrollbar { width: 3px; }
  .sheet-scroll::-webkit-scrollbar-track { background: transparent; }
  .sheet-scroll::-webkit-scrollbar-thumb { background: var(--ag-border); border-radius: 2px; }

  .sheet::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--ag-accent);
    opacity: 0.15;
    transform: scaleY(0);
    transform-origin: top;
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .trace[data-open="true"] .sheet::before {
    transform: scaleY(1);
  }
  .trace[data-state="error"] .sheet::before {
    background: var(--ag-warm);
    opacity: 0.2;
  }

  .sheet-inner {
    font-family: var(--font-mono);
    font-size: 11px;
    line-height: 1.6;
    color: var(--ag-ink-2);
    padding-right: 8px;
  }

  .out-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .section-label {
    font-size: 10px;
    letter-spacing: 0.01em;
    color: var(--ag-ink-3);
    font-weight: 500;
    font-family: var(--font-sans);
    margin-top: 4px;
    margin-bottom: -2px;
  }
  
  .out-kv {
    font-size: 11px;
    display: flex;
    flex-wrap: wrap; /* allow long values to wrap elegantly */
    align-items: baseline;
    gap: 6px;
  }

  .j-key {
    color: var(--ag-accent);
    font-weight: 500;
  }
  
  .j-punc {
    color: var(--ag-ink-3);
    opacity: 0.6;
  }

  .v {
    flex: 1;
    word-break: break-all;
  }

  .pre {
    white-space: pre-wrap;
  }

  .err-line {
    color: var(--ag-warm);
    opacity: 0.85;
  }

  .divider {
    height: 0;
    border-top: 0.5px solid var(--ag-border);
    margin: 4px 0;
    opacity: 0.5;
  }
  
  .sheet::-webkit-scrollbar { width: 3px; }
  .sheet::-webkit-scrollbar-track { background: transparent; }
  .sheet::-webkit-scrollbar-thumb { background: var(--ag-border); border-radius: 2px; }

  @keyframes traceIn {
    from { opacity: 0; transform: translateY(1px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
