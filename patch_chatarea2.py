import re
import codecs

with codecs.open('frontend/src/components/ChatArea.svelte', 'r', 'utf-8') as f:
    content = f.read()

new_html = """<div class="chat-system" class:is-idle={isIdle} class:is-active={!isIdle}>

  <div class="chat-scroll-region" aria-hidden={isIdle}>
    <div class="scroll-area" bind:this={chatWindow}>
      <div class="content">
        {#if !isIdle}
          <div class="message-list">
            {#each $messages as message, i (message.id)}
              <Message
                {message}
                isLive={$isStreaming && i === $messages.length - 1}
              />
            {/each}
          </div>
          {#if pendingConfirmation}
            <div class="confirmation-card" role="alert">
              <div class="confirmation-header">
                <span class="warning-icon" aria-hidden="true"></span>
                <span class="confirmation-title">Confirm command</span>
              </div>
              <code class="confirm-code">{pendingConfirmation.preview}</code>
              <p class="confirm-reason">{pendingConfirmation.reason}</p>

              <div class="confirm-actions">
                <button class="confirm-yes" onclick={() => handleConfirmation("YES")} disabled={confirmationBusy}>Yes, run it</button>
                <button class="confirm-cancel" onclick={() => handleConfirmation("No")} disabled={confirmationBusy}>Cancel</button>
              </div>
            </div>
          {/if}
          <div class="scroll-spacer"></div>
        {/if}
      </div>
    </div>
  </div>

  <div class="chat-input-region">
    {#if isIdle}
       <div class="idle-hero-wrapper" out:fade={{ duration: 350 }}>
         <IdleHero />
       </div>
    {/if}
    <div class="input-wrapper">
      <ChatInput
        disabled={$isStreaming || !!pendingConfirmation}
        showStop={$isStreaming}
        onsubmit={handleSubmit}
        onstop={handleStop}
      />
    </div>
    {#if pendingConfirmation}
      <p class="confirm-hint">Complete the confirmation above to continue</p>
    {/if}
  </div>
</div>"""

content = re.sub(r'<div class="chat-container">.*?</style>', new_html + '\n\n<style>', content, flags=re.DOTALL)

# Ensure transitions exist
if "import { fade }" not in content:
    content = content.replace('import IdleHero', 'import { fade } from "svelte/transition";\n  import IdleHero')

new_styles = """
  /* =======================================
     CORE SYSTEM ARCHITECTURE 
     ======================================= */
  .chat-system {
    width: 100%;
    height: 100%;
    position: relative;
    overflow: hidden;
  }

  /* --------------------------------------
     STATE 1: IDLE / HERO 
     True structural center. No translate hacks.
     -------------------------------------- */
  .chat-system.is-idle {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
  }
  
  .chat-system.is-idle .chat-scroll-region {
    display: none; /* Pure structural removal from spatial flow */
  }

  .chat-system.is-idle .chat-input-region {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    pointer-events: none;
  }

  .chat-system.is-idle .idle-hero-wrapper {
    margin-bottom: 24px;
    display: flex;
    justify-content: center;
    width: 100%;
  }

  /* --------------------------------------
     STATE 2: ACTIVE CONVERSATION
     Absolute layering for application scrolling.
     -------------------------------------- */
  .chat-system.is-active {
    display: block; 
  }

  .chat-system.is-active .chat-scroll-region {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    z-index: 1;
    animation: layoutFadeIn 0.5s ease forwards;
  }

  .chat-system.is-active .chat-input-region {
    position: absolute;
    bottom: 0; left: 0; right: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    z-index: 10;
    padding-top: 32px;
    padding-bottom: 16px;
    background: linear-gradient(to top, var(--ag-cream) 70%, transparent);
    pointer-events: none; 
  }
  
  .chat-system.is-active .input-wrapper {
    pointer-events: auto; /* Required */
  }

  @keyframes layoutFadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  """

content = content.replace('<style>', '<style>\n' + new_styles)
content = re.sub(r'  \.chat-container \{.*?\n  \}\n', '', content, flags=re.DOTALL)
content = re.sub(r'  \.input-zone \{.*?\n  \}\n', '', content, flags=re.DOTALL)

with codecs.open('frontend/src/components/ChatArea.svelte', 'w', 'utf-8') as f:
    f.write(content)
