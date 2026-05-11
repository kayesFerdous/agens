<script>
  export let tool = '';
  export let arguments_obj = {};
  export let result = null;
  export let error = null;
  export let status = 'running'; // 'running', 'done', 'error'
  export let isLast = true;

  let expanded = false;

  function toggleExpanded() {
    expanded = !expanded;
  }

  $: toolArgSummary = arguments_obj && Object.values(arguments_obj).length > 0
    ? String(Object.values(arguments_obj)[0]).split('\n')[0].slice(0, 40) + (String(Object.values(arguments_obj)[0]).length > 40 ? '…' : '')
    : '';
</script>

<div class="tool-row" class:has-timeline={!isLast}>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="row-head" onclick={toggleExpanded}>
    <div class="dot-wrapper">
      <div class="dot" class:done={status === 'done'} class:running={status === 'running'} class:err={status === 'error'}></div>
    </div>
    <span class="tool-name">{tool}</span>
    {#if toolArgSummary}
      <span class="tool-arg">{toolArgSummary}</span>
    {/if}
    
    <div class="pusher"></div>
    
    {#if arguments_obj || result || error}
      <svg class="chevron" class:open={expanded} width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="3 5 7 9 11 5"/>
      </svg>
    {/if}
    
    <span class="badge" class:done={status === 'done'} class:running={status === 'running'} class:err={status === 'error'}>{status}</span>
  </div>

  {#if arguments_obj || result || error}
    <div class="output" class:open={expanded}>
      <div class="out-section">
        {#if arguments_obj && Object.keys(arguments_obj).length > 0}
          <div class="section-label">Input</div>
          {#each Object.entries(arguments_obj) as [k, v]}
            <div class="out-kv">
              <span class="k">{k}</span>
              <span class="v pre input-val">{typeof v === 'object' ? JSON.stringify(v) : v}</span>
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
              <span class="k">error</span>
              <span class="v pre err">{error}</span>
            </div>
          {:else if typeof result === 'object'}
            {#each Object.entries(result).slice(0, 5) as [k, v]}
              <div class="out-kv">
                <span class="k">{k}</span>
                <span class="v pre">{typeof v === 'object' ? JSON.stringify(v) : v}</span>
              </div>
            {/each}
          {:else}
            <div class="out-kv">
              <span class="k">result</span>
              <span class="v pre">{result}</span>
            </div>
          {/if}
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .tool-row {
    background: var(--ag-accent-light);
    border: 0.5px solid rgba(123,110,170,0.20);
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 12px;
    color: var(--ag-accent);
    font-family: var(--font-sans);
  }

  .row-head {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    user-select: none;
    min-width: 0;
  }

  .dot-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--ag-accent-mid);
    flex-shrink: 0;
  }

  .dot.err {
    background: var(--ag-warm);
  }

  .tool-name {
    font-size: 12px;
    font-weight: 500;
    color: var(--ag-accent);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tool-arg {
    color: var(--ag-ink-3);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }

  .pusher {
    flex: 1;
  }

  .chevron {
    flex-shrink: 0;
    transition: transform 0.15s ease;
  }

  .chevron.open {
    transform: rotate(180deg);
  }

  .badge {
    background: var(--ag-accent-glow);
    color: var(--ag-accent);
    font-size: 10px;
    letter-spacing: 0.01em;
    border-radius: 6px;
    padding: 2px 8px;
    font-weight: 500;
    flex-shrink: 0;
  }

  .badge.err {
    background: var(--ag-warm-light);
    color: var(--ag-warm);
  }

  .output {
    display: none;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 0.5px solid rgba(123,110,170,0.20);
  }

  .output.open {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .section-label {
    font-size: 10px;
    letter-spacing: 0.01em;
    color: var(--ag-ink-3);
    font-weight: 500;
  }

  .out-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
    background: var(--ag-warm-white);
    border-radius: 8px;
    padding: 8px 10px;
    border: 0.5px solid var(--ag-border);
  }

  .out-kv {
    font-size: 12px;
    display: flex;
    align-items: flex-start;
    gap: 8px;
  }

  .k {
    color: var(--ag-ink-3);
    font-weight: 500;
    min-width: 60px;
  }

  .v {
    color: var(--ag-ink-2);
    font-family: var(--font-mono);
    word-break: break-all;
  }

  .pre {
    white-space: pre-wrap;
  }

  .err {
    color: var(--ag-warm);
  }

  .divider {
    height: 0;
    border-top: 0.5px solid var(--ag-border);
    margin: 2px 0;
  }
</style>
