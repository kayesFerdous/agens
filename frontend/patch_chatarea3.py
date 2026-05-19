import re
import codecs

with codecs.open('src/components/ChatArea.svelte', 'r', 'utf-8') as f:
    content = f.read()

# 1. Imports
content = content.replace('import WelcomeScreen from "./WelcomeScreen.svelte";', 'import { fade } from "svelte/transition";\n  import IdleHero from "./IdleHero.svelte";')

# 2. State
content = content.replace('let chatWindow;\n  // Track pending dangerous', 'let chatWindow;\n  let isIdle = $derived($messages.length === 0);\n  // Track pending dangerous')
content = content.replace('function handleSuggest(text) {\n    handleSubmit(text);\n  }', '')

# 3. HTML Layout
old_html_regex = r'<div class="chat-container">.*?</div>\n\n<style>'

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
            <!-- Render the inline confirmation card under the latest assistant message. -->
            <div class="confirmation-card" role="alert">
              <div class="confirmation-header">
                <span class="warning-icon" aria-hidden="true"></span>
                <span class="confirmation-title">Confirm command</span>
              </div>
              <code class="confirm-code">{pendingConfirmation.preview}</code>
              <p class="confirm-reason">{pendingConfirmation.reason}</p>

              <div class="confirm-actions">
                <button
                  class="confirm-yes"
                  onclick={() => handleConfirmation("YES")}
                  disabled={confirmationBusy}
                >
                  Yes, run it
                </button>
                <button
                  class="confirm-cancel"
                  onclick={() => handleConfirmation("No")}
                  disabled={confirmationBusy}
                >
                  Cancel
                </button>
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
       <div class="idle-hero-wrapper" out:fade={{ duration: 300 }}>
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
      <!-- Hint is only visible when authorization is in progress. -->
      <p class="confirm-hint">Complete the confirmation above to continue</p>
    {/if}
  </div>
</div>

<style>"""

content = re.sub(old_html_regex, new_html, content, flags=re.DOTALL)

# 4. CSS Updates
css_additions = """
  .chat-system {
    width: 100%;
    height: 100%;
    position: relative;
    overflow: hidden;
  }

  /* --- IDLE STATE --- */
  .chat-system.is-idle {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
  }

  .chat-system.is-idle .chat-scroll-region {
    display: none;
  }

  .chat-system.is-idle .chat-input-region {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    padding: 0 16px;
    z-index: 10;
  }

  .chat-system.is-idle .idle-hero-wrapper {
    margin-bottom: 40px; /* Spacious gap between hero and input */
    display: flex;
    justify-content: center;
    width: 100%;
  }

  /* By default .input-wrapper limits width, let's keep it structurally sound */
  .chat-system.is-idle .input-wrapper {
    width: 100%;
    max-width: 880px; /* Strong solid width for the input */
  }

  /* --- ACTIVE STATE --- */
  .chat-system.is-active {
    display: block;
  }

  .chat-system.is-active .chat-scroll-region {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    z-index: 1;
    animation: fadeIn 0.4s ease-out forwards;
  }

  .chat-system.is-active .chat-input-region {
    position: absolute;
    bottom: 0; left: 0; right: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-top: 32px;
    padding-bottom: 24px;
    background: linear-gradient(to top, var(--ag-cream) 70%, transparent);
    z-index: 10;
    pointer-events: none; /* Let background clicks pass through */
  }

  .chat-system.is-active .input-wrapper {
    width: 100%;
    max-width: 880px;
    padding: 0 16px;
    pointer-events: auto; /* Re-enable clicks for the input component */
  }
  
  .chat-system.is-active .confirm-hint {
    pointer-events: auto;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
"""

# Insert new CSS at the top of the <style> block
content = content.replace('<style>', '<style>\n' + css_additions)

# Clean up dead / legacy styles from the old layout
content = re.sub(r'  \.chat-container \{.*?\n  \}\n\n', '', content, flags=re.DOTALL)
content = re.sub(r'  \.welcome-wrapper \{.*?\n  \}\n\n', '', content, flags=re.DOTALL)
content = re.sub(r'  \.input-zone \{.*?\n  \}\n\n', '', content, flags=re.DOTALL)
content = re.sub(r'  \.input-wrapper \{.*?\n  \}\n\n', '', content, flags=re.DOTALL) # Removed since it's redeclared above

with codecs.open('src/components/ChatArea.svelte', 'w', 'utf-8') as f:
    f.write(content)
