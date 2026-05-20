<script>
  import ToolBlock from './ToolBlock.svelte';
  import ThinkingIndicator from './ThinkingIndicator.svelte';
  import MarkdownRenderer from './MarkdownRenderer.svelte';
  import Logo from './Logo.svelte';

  export let message;
  export let isLive = false;

  
  let wasLive = false;
  $: {
    if (isLive) {
      wasLive = true;
      
    } else if (wasLive && !isLive) {
      wasLive = false;
      
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
    <div class="avatar ai-avatar" aria-hidden="true">
      <Logo width="20px" height="20px" />
    </div>
    <div class="ai-body">
    {#if message.isThinking}
      <ThinkingIndicator />
    {/if}

    {#if hasTools}
      <div class="trace-wrapper">
        

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
      </div>
    {/if}

    {#if message.content && !message.isThinking}
      <div class="content">
        <MarkdownRenderer content={message.content} isLive={isLive} />
      </div>
    {/if}
    </div>
  </section>
{/if}

<style>
  .user-msg,
  .ai-msg,
  .status-msg {
    width: 100%;
    display: flex;
    gap: 12px;
    animation: slideUp 0.24s cubic-bezier(0.16, 1, 0.3, 1) both;
  }

  .user-msg {
    flex-direction: row-reverse;
    align-items: flex-end;
  }

  .ai-msg {
    align-items: flex-start;
  }

  .avatar {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 500;
    font-size: 13px;
    flex-shrink: 0;
  }

  .ai-avatar {
    background: var(--ag-accent-light);
    color: var(--ag-accent);
    border: 0.5px solid rgba(123,110,170,0.25);
  }

  .bubble {
    padding: 10px 16px;
    font-size: 14px;
    line-height: 1.7;
    max-width: min(72%, 660px);
    white-space: pre-wrap;
    word-break: break-word;
  }

  .user-msg .bubble {
    background: var(--ag-ink);
    color: var(--ag-cream);
    border-radius: 18px 18px 4px 18px;
  }

  .ai-body {
    min-width: 0;
    max-width: min(76%, 700px);
  }

  .content {
    background: var(--ag-surface);
    color: var(--ag-ink);
    border-radius: 18px 18px 18px 4px;
    padding: 12px 16px;
    border: 0.5px solid rgba(60,50,30,0.08);
  }

  .status-msg {
    justify-content: center;
  }

  .status-bubble {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    max-width: min(680px, 100%);
    padding: 7px 12px;
    border-radius: 8px;
    background: var(--ag-accent-light);
    border: 0.5px solid rgba(123,110,170,0.20);
    color: var(--ag-accent);
    font-size: 12px;
  }

  .status-icon {
    flex: 0 0 auto;
  }

  .trace-wrapper {
    margin: 0 0 8px;
  }

  .trace-toggle {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    margin: 0 0 6px;
    color: var(--ag-ink-3);
    font-size: 12px;
    cursor: pointer;
  }

  .trace-chevron {
    transition: transform 0.16s ease;
  }

  .trace-chevron.open {
    transform: rotate(90deg);
  }

  .tools-timeline {
    display: flex;
    flex-direction: column;
    max-width: 480px;
    align-self: flex-start;
    margin: 2px 0;
  }

  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  :global(.bubble p) {
    margin: 0 0 12px;
  }
  :global(.bubble p:last-child) {
    margin-bottom: 0;
  }
  :global(.bubble code) {
    background: var(--ag-accent-light);
    color: var(--ag-accent-deep);
    border-radius: 4px;
    padding: 2px 6px;
    font-family: var(--font-mono);
    font-size: 0.9em;
  }
  :global(.user .bubble code) {
    background: var(--ag-ink-2);
    color: var(--ag-warm-white);
  }

  @media (max-width: 720px) {
    .avatar {
      display: none;
    }

    .bubble,
    .ai-body {
      max-width: 100%;
    }
  }

</style>
