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
          <div class="section-label">INPUT</div>
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
          <div class="section-label">OUTPUT</div>
          
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
    font-family: inherit;
    position: relative;
    padding-bottom: 4px;
  }
  
  .tool-row.has-timeline::before {
    content: "";
    position: absolute;
    left: 4px; /* Center of 8px dot */
    top: 14px; /* Start below the dot */
    bottom: -6px; /* Stretch exactly to the center of the next dot */
    width: 1px;
    background: var(--border-main);
    z-index: 0;
  }

  .row-head {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 0;
    user-select: none;
    position: relative;
    z-index: 10;
    cursor: pointer;
  }
  
  .row-head:hover .tool-name { color: var(--text-highlight); }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .dot.done { background: var(--accent-primary); }
  .dot.running { background: var(--text-tertiary); animation: glow 1.2s infinite; }
  .dot.err { background: var(--status-err); }
  
  @keyframes glow {
    0%, 100% { opacity: 1; }
    50% { opacity: .25; }
  }

  .tool-name {
    font-size: 13px;
    font-family: monospace;
    color: var(--text-primary);
    flex-shrink: 0;
    transition: color 0.2s;
  }
  
  .tool-arg {
    font-size: 12px;
    color: var(--text-tertiary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    font-family: monospace;
  }
  .tool-arg::before { content: "· "; }

  .pusher {
    flex: 1;
  }

  .badge {
    font-size: 10px;
    padding: 1px 7px;
    border-radius: 3px;
    flex-shrink: 0;
    letter-spacing: .03em;
    text-transform: uppercase;
    font-family: 'Inter', sans-serif;
  }
  .badge.done { background: var(--badge-done-bg); color: var(--accent-primary); border: 0.5px solid var(--badge-done-border); }
  .badge.running { background: var(--badge-done-bg); color: var(--accent-primary); border: 0.5px solid var(--badge-done-border); }
  .badge.err { background: var(--badge-err-bg); color: var(--status-err); border: 0.5px solid var(--badge-err-border); }

  .chevron {
    transition: transform .18s, color .15s;
    display: block;
    color: var(--text-tertiary);
    margin-right: 4px;
  }
  .row-head:hover .chevron { color: var(--text-secondary); }
  .chevron.open { transform: rotate(180deg); }

  .output {
    display: none;
    padding: 8px 0 16px 20px; /* Aligns with tool-name cleanly */
  }
  .output.open { display: block; }

  .out-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-left: 6px;
  }

  .section-label {
    font-size: 10px;
    color: var(--text-tertiary);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    font-family: 'Inter', sans-serif;
    margin-bottom: 2px;
    margin-top: 4px;
  }

  .divider {
    height: 1px;
    background: var(--border-main);
    margin: 4px 0;
    width: 100%;
  }

  .out-kv {
    display: flex;
    align-items: baseline;
    gap: 16px;
    font-family: monospace;
    font-size: 12px;
  }
  
  .k { 
    color: var(--text-secondary); 
    white-space: nowrap;
    width: 110px; /* increased to prevent overlap with value */
    flex-shrink: 0;
  }
  
  .v { 
    color: var(--text-secondary); 
  }
  
  .v.input-val {
    color: var(--accent-primary);
  }
  
  .v.pre {
    white-space: pre-wrap; 
    word-break: break-all;
  }
  .v.err { 
    color: var(--status-err); 
  }
</style>
