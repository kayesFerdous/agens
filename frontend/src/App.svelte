<script>
  
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { activeSessionId, theme, messages, activePage, restoredConfirmation, noApiKeys, settingsTab } from './lib/store.js';
  import { getSession, shutdownAssistant, getSetupStatus } from './lib/api.js';
  import { sessionService } from './lib/sessionService.svelte.js';

  let showShutdownConfirm = false;
  let shutdownPending = false;
  let shutdownError = null;
  let setupLoading = true;

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
        noApiKeys.set(!!setup.no_api_keys);
        if (get(noApiKeys)) {
          const params = new URLSearchParams(window.location.search);
          const page = params.get('page');
          const tab = params.get('tab');
          if (page) activePage.set(page);
          if (tab) settingsTab.set(tab);
          return;
        }

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
        const tab = params.get('tab');
        if (tab) {
          settingsTab.set(tab);
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

      if (!$noApiKeys && sid !== $activeSessionId) {
        activeSessionId.set(sid);
        loadSession(sid);
      }

      if (page !== $activePage) {
        activePage.set(page);
      }
      settingsTab.set(params.get('tab') || 'general');
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  });

  $: {
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      const currentSid = url.searchParams.get('session');
      const currentPage = url.searchParams.get('page') || 'chat';
      const currentTab = url.searchParams.get('tab') || 'general';
      
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

      if ($activePage === 'settings') {
        if (currentTab !== $settingsTab) {
          url.searchParams.set('tab', $settingsTab);
          changed = true;
        }
      } else if (url.searchParams.has('tab')) {
        url.searchParams.delete('tab');
        changed = true;
      }

      if (changed) {
        window.history.pushState({ sessionId: $activeSessionId, page: $activePage }, '', url);
      }
    }
  }

  // Reload messages when activeSessionId changes
  $: {
    if (!$noApiKeys) {
      loadSession($activeSessionId);
    }
  }
</script>

<div class="app-layout">
  <Sidebar />
  
  <div class="main-content">
    <header class="top-nav">
      <div class="left">
        <span class="app-title">Agens</span>
      </div>
      
      <div class="right">
        <div class="engine-status">
          <span class="dot"></span>
          Local engine active
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
          
          <button class="icon-btn" aria-label="Settings" onclick={() => activePage.set('settings')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
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
      {:else if $activePage === 'settings'}
        <SettingsPage />
      {:else if $noApiKeys}
        <SetupPage />
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

  .app-layout {
    display: flex;
    width: 100%;
    height: 100vh;
    overflow: hidden;
  }

  .main-content {
    flex: 1;
    margin-left: 264px;
    display: flex;
    flex-direction: column;
    position: relative;
    background: var(--ag-cream);
  }

  .top-nav {
    height: 56px;
    background: var(--ag-warm-white);
    border-bottom: 0.5px solid var(--ag-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    z-index: 40;
  }

  .app-title {
    font-weight: 400;
    font-size: 13px;
    color: var(--ag-ink-3);
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
    font-size: 11px;
    font-weight: 500;
    color: var(--ag-ink-3);
    letter-spacing: 0.01em;
  }

  .engine-status .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background-color: var(--ag-accent);
  }

  .nav-icons {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .icon-btn {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    background: transparent;
    border: 0.5px solid transparent;
    color: var(--ag-ink-3);
    cursor: pointer;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color 0.1s;
  }

  .icon-btn:hover {
    color: var(--ag-ink);
    background: var(--ag-surface);
    border-color: var(--ag-border);
  }

  .icon-btn.danger:hover {
    color: var(--ag-warm);
  }

  .shutdown-modal-overlay {
    position: fixed;
    inset: 0;
    z-index: 5000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    background: rgba(28, 24, 20, 0.4);
    backdrop-filter: blur(8px);
  }

  .shutdown-modal {
    width: min(420px, 100%);
    background: var(--ag-warm-white);
    border: 0.5px solid var(--ag-border);
    border-radius: 24px;
    padding: 24px;
  }

  .shutdown-modal h2 {
    margin: 0 0 8px;
    color: var(--ag-ink);
    font-size: 18px;
    font-weight: 500;
  }

  .shutdown-modal p {
    margin: 0;
    color: var(--ag-ink-2);
    font-size: 14px;
    line-height: 1.5;
  }

  .shutdown-error {
    margin-top: 12px !important;
    color: var(--ag-warm) !important;
  }

  .shutdown-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 24px;
  }

  .shutdown-cancel,
  .shutdown-confirm {
    border-radius: 12px;
    padding: 9px 14px;
    font: inherit;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
  }

  .shutdown-cancel {
    border: 0.5px solid var(--ag-border);
    background: transparent;
    color: var(--ag-ink);
  }
  .shutdown-cancel:hover { background: var(--ag-surface); }

  .shutdown-confirm {
    border: 0.5px solid rgba(201,124,74,0.25);
    background: var(--ag-warm-light);
    color: var(--ag-warm);
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
    color: var(--ag-ink-2);
    font-size: 14px;
  }

  /* Clear ugly glow artifacts entirely */
  .glow-tr, .glow-bl { display: none; }

</style>
