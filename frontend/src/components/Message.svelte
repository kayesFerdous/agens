<script>
  import ToolBlock from './ToolBlock.svelte';
  import ThinkingIndicator from './ThinkingIndicator.svelte';
  import MarkdownRenderer from './MarkdownRenderer.svelte';

  export let message;
  export let isLive = false;

  let traceExpanded = false;
  let wasLive = false;
  $: {
    if (isLive) {
      wasLive = true;
      traceExpanded = true;
    } else if (wasLive && !isLive) {
      wasLive = false;
      traceExpanded = false;
    }
  }

  $: hasTools = (message.toolBlocks && message.toolBlocks.length > 0) || (message.tool_calls && message.tool_calls.length > 0);
</script>

{#if message.role === 'user'}
  <section class="user-msg">
    <div class="bubble">
      {message.content}
    </div>
  </section>
{:else if message.role === 'status'}
  <section class="status-msg">
    <div class="status-bubble">
      <svg class="status-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="16" x2="12" y2="12"></line>
        <line x1="12" y1="8" x2="12.01" y2="8"></line>
      </svg>
      <span class="status-text">{message.content}</span>
    </div>
  </section>
{:else}
  <section class="ai-msg">
    {#if message.isThinking}
      <ThinkingIndicator />
    {/if}

    {#if hasTools}
      <div class="trace-wrapper">
        {#if !isLive}
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div class="trace-toggle" onclick={() => traceExpanded = !traceExpanded}>
            trace
            <svg class="trace-chevron" class:open={traceExpanded} width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="5 3 9 7 5 11" />
            </svg>
          </div>
        {/if}

        {#if traceExpanded || isLive}
          <div class="tools-timeline">
            {#if message.toolBlocks}
              {#each message.toolBlocks as block, index}
                <ToolBlock 
                  tool={block.tool || block.function?.name || block.name} 
                  arguments_obj={block.arguments} 
                  result={block.result}
                  error={block.error}
                  status={block.status} 
                  isLast={index === message.toolBlocks.length - 1}
                />
              {/each}
            {/if}
            {#if message.tool_calls}
              {#each message.tool_calls as call, index}
                <ToolBlock 
                  tool={call.tool || call.function?.name || call.name} 
                  arguments_obj={call.arguments} 
                  result={call.result}
                  error={call.error}
                  status={call.error ? 'error' : 'done'} 
                  isLast={index === message.tool_calls.length - 1}
                />
              {/each}
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    {#if message.content && !message.isThinking}
      <div class="content">
        <MarkdownRenderer content={message.content} isLive={isLive} />
      </div>
    {/if}
  </section>
{/if}

<style>
  .user-msg {
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-self: flex-end;
    max-width: 85%;
    font-family: 'Inter', sans-serif;
  }

  .bubble {
    background: var(--bg-surface);
    padding: 12px 18px;
    border-radius: 10px;
    border-bottom-right-radius: 2px;
    border: 0.5px solid var(--border-main);
    color: var(--text-primary);
    line-height: 1.6;
    font-size: 15px;
  }

  .ai-msg {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 24px;
    font-family: 'Inter', sans-serif;
  }

  .status-msg {
    display: flex;
    justify-content: center;
    width: 100%;
    margin: 8px 0;
  }

  .status-bubble {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: var(--surface-container-high);
    border: 1px solid var(--border-main);
    border-radius: 6px;
    color: var(--text-secondary);
    font-size: 13px;
    font-family: 'Inter', sans-serif;
    animation: fadeSlideIn 0.3s ease-out;
  }

  .status-icon {
    color: var(--accent-primary);
  }

  .status-text {
    line-height: 1.4;
  }

  @keyframes fadeSlideIn {
    from {
      opacity: 0;
      transform: translateY(4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .tools-timeline {
    display: flex;
    flex-direction: column;
    padding-left: 12px;
  }

  .trace-toggle {
    font-size: 11px;
    font-family: monospace;
    color: var(--text-tertiary);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-bottom: 12px;
    user-select: none;
    transition: color 0.15s;
  }
  .trace-toggle:hover {
    color: var(--text-secondary);
  }

  .trace-chevron {
    transition: transform 0.15s;
  }
  .trace-chevron.open {
    transform: rotate(90deg);
  }

  .content {
    color: var(--text-primary);
    line-height: 1.8;
    font-size: 14px;
  }

  /* Markdown styles are fully managed by MarkdownRenderer.svelte */
</style>
