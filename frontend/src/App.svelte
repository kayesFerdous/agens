<script>
  import '@fontsource/inter';
  import { onMount } from 'svelte';
  import { activeSessionId, theme, messages, activePage, restoredConfirmation } from './lib/store.js';
  import { getSession, shutdownAssistant, getSetupStatus } from './lib/api.js';
  import { sessionService } from './lib/sessionService.svelte.js';

  let showShutdownConfirm = false;
  let shutdownPending = false;
  let shutdownError = null;
  let setupLoading = true;
  let noApiKeys = false;

  function toggleTheme() {
    theme.update(t => t === 'dark' ? 'light' : 'dark');
  }

  async function requestShutdown() {
    if (shutdownPending) return;
    shutdownPending = true;
    shutdownError = null;
    try {
      const result = await shutdownAssistant();
      if (!result.ok) {
        shutdownError = result.data?.detail ?? 'Shutdown request failed.';
        shutdownPending = false;
      }
    } catch {
      shutdownError = 'Unable to reach the local server.';
      shutdownPending = false;
    }
  }
  
  import Sidebar from './components/Sidebar.svelte';
  import ChatArea from './components/ChatArea.svelte';
  import SettingsPage from './components/settings/SettingsPage.svelte';
  import SetupPage from './components/SetupPage.svelte';

  async function loadSession(id) {
    if (!id) {
      messages.set([]);
      restoredConfirmation.set(null);
      return;
    }
    try {
      const data = await getSession(id);
      if (data && data.messages) {
        messages.set(data.messages);

        // ── Restore confirmation UI on reload (if genuinely still pending) ────
        //
        // A tool_call with status "awaiting_user_confirmation" is written to the
        // DB when the agent intercepts a dangerous command.  However that record
        // is NEVER updated when the user later confirms or cancels — only a new
        // assistant message is appended.  We therefore must apply two guards:
        //
        //   Guard 1 – already acted on:
        //     If the assistant message that contains the pending tool_call is NOT
        //     the very last message in the thread, the user already replied (YES
        //     or NO) and new messages were appended.  Skip restoration.
        //
        //   Guard 2 – TTL expired:
        //     The backend TTL is 300 s (CONFIRMATION_TTL_SECONDS).  If the
        //     assistant message is older than that the backend will reject any
        //     "YES" anyway, so showing the card would be misleading.  Skip.

        const CONFIRMATION_TTL_MS = 300_000; // mirrors backend CONFIRMATION_TTL_SECONDS
        const msgs = data.messages; // already in chronological order from the API

        // Find the index of the last assistant message that has a pending tc.
        let pendingTc = null;
        let pendingMsgIndex = -1;
        for (let i = msgs.length - 1; i >= 0; i--) {
          const m = msgs[i];
          if (m.role !== 'assistant') continue;
          const tc = m.tool_calls?.find(
            t => t.result?.status === 'awaiting_user_confirmation'
          );
          if (tc) {
            pendingTc = tc;
            pendingMsgIndex = i;
            break;
          }
        }

        let shouldRestore = false;
        if (pendingTc && pendingMsgIndex !== -1) {
          // Guard 1: must be the very last message in the thread.
          const isLastMessage = pendingMsgIndex === msgs.length - 1;

          // Guard 2: must be within the TTL window.
          const msgAge = Date.now() - new Date(msgs[pendingMsgIndex].created_at).getTime();
          const withinTtl = msgAge < CONFIRMATION_TTL_MS;

          shouldRestore = isLastMessage && withinTtl;
        }

        if (shouldRestore) {
          restoredConfirmation.set({
            preview: pendingTc.result.preview
              ?? pendingTc.arguments?.command
              ?? '(unknown command)',
            reason: pendingTc.result.reason ?? 'Dangerous command — requires confirmation.',
            requires_sudo_auth: !!(pendingTc.arguments?.command?.match(/\bsudo\b/)),
          });
        } else {
          restoredConfirmation.set(null);
        }
        // ─────────────────────────────────────────────────────────────────────
      }
    } catch (err) {
      console.error('Failed to load session:', err);
    }
  }

  onMount(() => {
    (async () => {
      try {
        const setup = await getSetupStatus();
        noApiKeys = !!setup.no_api_keys;
        if (noApiKeys) return;

        await sessionService.loadInitial();
        
        
        // Load from URL if present
        const params = new URLSearchParams(window.location.search);
        const sid = params.get('session');
        if (sid) {
          activeSessionId.set(sid);
          await loadSession(sid);
        }

        const page = params.get('page');
        if (page) {
          activePage.set(page);
        }
      } catch (err) {
        console.error('Failed to load sessions:', err);
      } finally {
        setupLoading = false;
      }
    })();

    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search);
      const sid = params.get('session');
      const page = params.get('page') || 'chat';

      if (!noApiKeys && sid !== $activeSessionId) {
        activeSessionId.set(sid);
        loadSession(sid);
      }

      if (page !== $activePage) {
        activePage.set(page);
      }
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  });

  $: {
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      const currentSid = url.searchParams.get('session');
      const currentPage = url.searchParams.get('page') || 'chat';
      
      let changed = false;

      // Sync Session
      if ($activeSessionId) {
        if (currentSid !== $activeSessionId) {
          url.searchParams.set('session', $activeSessionId);
          changed = true;
        }
      } else if (currentSid) {
        url.searchParams.delete('session');
        changed = true;
      }

      // Sync Page
      if (currentPage !== $activePage) {
        if ($activePage === 'chat') {
          url.searchParams.delete('page');
        } else {
          url.searchParams.set('page', $activePage);
        }
        changed = true;
      }

      if (changed) {
        window.history.pushState({ sessionId: $activeSessionId, page: $activePage }, '', url);
      }
    }
  }

  // Reload messages when activeSessionId changes
  $: {
    if (!noApiKeys) {
      loadSession($activeSessionId);
    }
  }
</script>

<div class="app-layout">
  <Sidebar />
  
  <div class="main-content">
    <header class="top-nav">
      <div class="left">
        <span class="app-title">The intelligence layer</span>
      </div>
      
      <div class="right">
        <div class="engine-status">
          <span class="dot"></span>
          Local Engine Active
        </div>
        
        <div class="nav-icons">
          <button class="icon-btn" aria-label="Toggle theme" onclick={toggleTheme}>
            {#if $theme === 'dark'}
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="5"></circle>
                <line x1="12" y1="1" x2="12" y2="3"></line>
                <line x1="12" y1="21" x2="12" y2="23"></line>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                <line x1="1" y1="12" x2="3" y2="12"></line>
                <line x1="21" y1="12" x2="23" y2="12"></line>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
              </svg>
            {:else}
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
              </svg>
            {/if}
          </button>
          <button class="icon-btn" aria-label="Cloud sync">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.36 8.04A5.994 5.994 0 0 0 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM10 17l-3.5-3.5 1.41-1.41L10 14.17 15.18 9l1.41 1.41L10 17z"/>
            </svg>
          </button>
          <button class="icon-btn danger" aria-label="Shutdown assistant" title="Shutdown assistant" onclick={() => showShutdownConfirm = true}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path>
              <line x1="12" y1="2" x2="12" y2="12"></line>
            </svg>
          </button>
        </div>
      </div>
    </header>

    <div class="chat-wrapper">
      <!-- Glow effects -->
      <div class="glow-tr"></div>
      <div class="glow-bl"></div>
      
      {#if setupLoading}
        <div class="setup-loading">Checking setup...</div>
      {:else if noApiKeys}
        <SetupPage />
      {:else if $activePage === 'settings'}
        <SettingsPage />
      {:else}
        <ChatArea />
      {/if}
    </div>
  </div>
</div>

{#if showShutdownConfirm}
  <div class="shutdown-modal-overlay" role="presentation">
    <div class="shutdown-modal" role="dialog" aria-modal="true" aria-labelledby="shutdown-title">
      <h2 id="shutdown-title">Shutdown assistant?</h2>
      <p>This stops the local assistant process and cancels active streams.</p>
      {#if shutdownError}
        <p class="shutdown-error">{shutdownError}</p>
      {/if}
      <div class="shutdown-actions">
        <button type="button" class="shutdown-cancel" onclick={() => showShutdownConfirm = false} disabled={shutdownPending}>
          Cancel
        </button>
        <button type="button" class="shutdown-confirm" onclick={requestShutdown} disabled={shutdownPending}>
          {shutdownPending ? 'Shutting down...' : 'Shutdown'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  :global(:root) {
    --bg-base: #08080a;
    --bg-surface: #0f0f12;
    --border-main: #1c1c22;
    --text-primary: #e8e6e1;
    --text-highlight: #ffffff;
    --text-secondary: #a0a0ab;
    --text-tertiary: #6b6b76;
    --accent-primary: #D97757;
    --accent-gold: var(--accent-primary);
    --status-err: #c0574f;
    
    --bg-input: #141418;
    --text-placeholder: #2e2e3a;
    --text-disclaimer: #2a2a35;
    
    --badge-done-bg: #1e1a13;
    --badge-done-border: #3a3020;
    
    --badge-err-bg: #1a1010;
    --badge-err-border: #3a1515;
    
    --bg-nav: rgba(14, 14, 14, 0.7);
    --glow-bg: rgba(217, 119, 87, 0.05);
    --shadow-input: 0 12px 24px rgba(0, 0, 0, 0.3);
    
    --surface-container-high: #141418;
    
    /* Legacy fallbacks for components */
    --background: var(--bg-base);
    --surface: var(--bg-surface);
    --on-surface: var(--text-primary);
    --on-surface-variant: var(--text-secondary);
    --outline-variant: var(--border-main);
    --surface-container: #111116;
    --surface-bright: #1b1b22;
  }

  :global(:root[data-theme="light"]) {
    --bg-base: #f8f7f4;
    --bg-surface: #ffffff;
    --border-main: #e1ded6;
    --text-primary: #1f1f21;
    --text-highlight: #000000;
    --text-secondary: #5a5854;
    --text-tertiary: #84817a;
    --accent-primary: #D97757;
    --accent-gold: var(--accent-primary);
    --status-err: #b14840;
    
    --bg-input: #ffffff;
    --text-placeholder: #a39f97;
    --text-disclaimer: #8c8983;
    
    --badge-done-bg: #faf7f0;
    --badge-done-border: #e0d2b6;
    
    --badge-err-bg: #fbeded;
    --badge-err-border: #f0b0ab;
    
    --bg-nav: rgba(248, 247, 244, 0.85);
    --glow-bg: rgba(217, 119, 87, 0.15);
    --shadow-input: 0 12px 24px rgba(0, 0, 0, 0.06);
    
    --surface-container-high: #fbf9f6;
    
    /* Legacy fallbacks for components */
    --background: var(--bg-base);
    --surface: var(--bg-surface);
    --on-surface: var(--text-primary);
    --on-surface-variant: var(--text-secondary);
    --outline-variant: var(--border-main);
    --surface-container: #f0eee9;
    --surface-bright: #ffffff;
  }



  :global(body) {
    margin: 0;
    padding: 0;
    background-color: var(--bg-base);
    color: var(--text-primary);
    font-family: 'Inter', sans-serif;
    -webkit-font-smoothing: antialiased;
    overflow: hidden; /* Prevent body scroll, everything handled internally */
    transition: background-color 0.3s ease, color 0.3s ease;
  }

  :global(*) {
    box-sizing: border-box;
  }

  :global(::selection) {
    background: rgba(217, 119, 87, 0.3); /* primary matching */
  }

  .app-layout {
    display: flex;
    width: 100vw;
    height: 100vh;
  }

  .main-content {
    flex: 1;
    margin-left: 264px; /* match sidebar width */
    display: flex;
    flex-direction: column;
    position: relative;
    background: var(--bg-surface);
    border-left: 1px solid var(--border-main);
  }

  .top-nav {
    height: 56px;
    background: var(--bg-nav);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border-bottom: 1px solid var(--border-main);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    z-index: 40;
  }

  .app-title {
    font-weight: 600;
    font-size: 14px;
    color: var(--text-primary);
  }

  .right {
    display: flex;
    align-items: center;
    gap: 20px;
  }

  .engine-status {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 12px;
    background: var(--surface-container-high);
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #10b981; /* emerald-500 matching design */
  }

  .nav-icons {
    display: flex;
    align-items: center;
    gap: 16px;
    opacity: 0.5;
  }

  .icon-btn {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color 0.2s;
  }

  .icon-btn:hover {
    color: var(--text-primary);
  }

  .icon-btn.danger:hover {
    color: var(--status-err);
  }

  .shutdown-modal-overlay {
    position: fixed;
    inset: 0;
    z-index: 5000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(8px);
  }

  .shutdown-modal {
    width: min(420px, 100%);
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 12px;
    padding: 22px;
    box-shadow: 0 24px 70px rgba(0, 0, 0, 0.45);
  }

  .shutdown-modal h2 {
    margin: 0 0 8px;
    color: var(--text-primary);
    font-size: 18px;
    font-weight: 700;
  }

  .shutdown-modal p {
    margin: 0;
    color: var(--text-secondary);
    font-size: 14px;
    line-height: 1.5;
  }

  .shutdown-error {
    margin-top: 12px !important;
    color: var(--status-err) !important;
  }

  .shutdown-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 24px;
  }

  .shutdown-cancel,
  .shutdown-confirm {
    border-radius: 8px;
    padding: 9px 14px;
    font: inherit;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }

  .shutdown-cancel {
    border: 1px solid var(--border-main);
    background: transparent;
    color: var(--text-primary);
  }

  .shutdown-confirm {
    border: 1px solid var(--badge-err-border);
    background: var(--badge-err-bg);
    color: var(--status-err);
  }

  .shutdown-cancel:disabled,
  .shutdown-confirm:disabled {
    cursor: not-allowed;
    opacity: 0.65;
  }

  .chat-wrapper {
    flex: 1;
    position: relative;
    overflow: hidden;
  }

  .setup-loading {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-secondary);
    font-size: 14px;
  }

  /* Aesthetic Decorative Elements */
  .glow-tr {
    position: absolute;
    top: 25%;
    right: -128px;
    width: 500px;
    height: 500px;
    background: var(--glow-bg);
    filter: blur(120px);
    border-radius: 50%;
    pointer-events: none;
    z-index: -1;
  }

  .glow-bl {
    position: absolute;
    bottom: -128px;
    left: -128px;
    width: 500px;
    height: 500px;
    background: var(--glow-bg);
    filter: blur(120px);
    border-radius: 50%;
    pointer-events: none;
    z-index: -1;
  }
</style>
