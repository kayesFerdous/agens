<script>
  import { activeSessionId, messages, activePage, isSidebarOpen } from '../lib/store.js';
  import { sessionService } from '../lib/sessionService.svelte.js';
  import InfiniteScroll from './InfiniteScroll.svelte';
  import Logo from './Logo.svelte';

  function formatTime(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  function closeSidebarOnMobile() {
    if (window.innerWidth <= 820) {
      isSidebarOpen.set(false);
    }
  }

  function handleNewChat() {
    activeSessionId.set(null);
    messages.set([]);
    activePage.set('chat');
    closeSidebarOnMobile();
  }

  function selectSession(id) {
    activeSessionId.set(id);
    activePage.set('chat');
    closeSidebarOnMobile();
  }

  let sessionToDelete = null;

  function confirmDelete(e, id) {
    e.stopPropagation();
    sessionToDelete = id;
  }

  function cancelDelete() {
    sessionToDelete = null;
  }

  async function executeDelete() {
    if (!sessionToDelete) return;
    const id = sessionToDelete;
    sessionToDelete = null; // close modal right away
    await sessionService.remove(id);
    if ($activeSessionId === id) {
      activeSessionId.set(null);
      messages.set([]);
    }
  }
</script>

<aside class="sidebar" class:open={$isSidebarOpen}>
  <div class="brand">
    <div class="brand-icon">
      <Logo width="18" height="18" />
    </div>
    <div>
      <h1 class="brand-name">Agens</h1>
      <p class="brand-version">v1.0.4 stable</p>
    </div>
  </div>

  <button class="new-chat-btn" onclick={handleNewChat}>
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
      <line x1="12" y1="5" x2="12" y2="19"/>
      <line x1="5" y1="12" x2="19" y2="12"/>
    </svg>
    <span>New Chat</span>
  </button>

  <nav class="sessions-list">
    <p class="sessions-label">Recent chats</p>
    {#each sessionService.sessions as session (session.id)}
      <div
        class="session-item"
        class:active={$activeSessionId === session.id}
        onclick={() => selectSession(session.id)}
        onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && selectSession(session.id)}
        role="button"
        tabindex="0"
      >
        <div class="session-info">
          <span class="session-title">{session.title || 'New conversation'}</span>
          <span class="session-time">{formatTime(session.created_at)}</span>
        </div>
        <button class="delete-btn" aria-label="Delete session" onclick={(e) => confirmDelete(e, session.id)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
    {/each}
    <InfiniteScroll 
      hasMore={sessionService.hasMore} 
      loading={sessionService.loading} 
      onloadmore={() => sessionService.loadMore()} 
    />
  </nav>

  
</aside>

{#if sessionToDelete}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="modal-overlay" onclick={cancelDelete}>
    <div class="modal-content" onclick={(e) => e.stopPropagation()}>
      <div class="modal-header">
        <div class="modal-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 6h18"></path>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            <line x1="10" y1="11" x2="10" y2="17"></line>
            <line x1="14" y1="11" x2="14" y2="17"></line>
          </svg>
        </div>
        <h2 class="modal-title">Delete Chat</h2>
      </div>
      <p class="modal-body">
        Delete this conversation? This action cannot be undone.
      </p>
      <div class="modal-actions">
        <button class="btn-cancel" onclick={cancelDelete}>Cancel</button>
        <button class="btn-delete" onclick={executeDelete}>Delete</button>
      </div>
    </div>
  </div>
{/if}

<style>

  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    width: 264px;
    height: 100vh;
    box-sizing: border-box;
    background: var(--ag-surface);
    border-right: 0.5px solid var(--ag-border);
    display: flex;
    flex-direction: column;
    padding: 24px 16px;
    gap: 32px;
    z-index: 50;
    font-family: var(--font-sans);
    -webkit-font-smoothing: antialiased;
    transform: translateX(-100%);
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 8px;
  }

  .brand-icon {
    width: 32px;
    height: 32px;
    border-radius: 6px;
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--ag-ink);
  }

  .brand-name {
    font-size: 16px;
    font-weight: 400;
    letter-spacing: -0.02em;
    color: var(--ag-ink);
    margin: 0;
  }

  .brand-version {
    font-size: 10px;
    color: var(--ag-ink-3);
    letter-spacing: 0.01em;
    margin: 2px 0 0;
    font-weight: 500;
  }

  .new-chat-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 16px;
    border-radius: 12px;
    background: var(--ag-accent-light);
    color: var(--ag-accent);
    border: 0.5px solid rgba(123,110,170,0.25);
    font-weight: 500;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.15s ease;
    font-family: inherit;
  }
  .new-chat-btn svg {
    color: var(--ag-accent);
  }

  .new-chat-btn:hover {
    background: var(--ag-accent-mid);
    color: var(--ag-cream);
  }

  .sessions-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow-y: auto;
    flex: 1;
  }

  .sessions-label {
    font-size: 10px;
    font-weight: 500;
    color: var(--ag-ink-3);
    padding: 0 8px 8px;
    letter-spacing: 0.01em;
    margin: 0;
  }

  .session-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border-radius: 8px;
    color: var(--ag-ink-2);
    font-size: 13px;
    font-weight: 400;
    cursor: pointer;
    transition: all 0.1s ease;
    text-decoration: none;
    border: 0.5px solid transparent;
  }

  .session-item:hover {
    background: rgba(60,50,30,0.05);
  }

  .session-item.active {
    background: var(--ag-warm-white);
    border: 0.5px solid var(--ag-border);
    color: var(--ag-ink);
  }

  .session-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
    min-width: 0;
  }

  .session-title {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .session-time {
    font-size: 11px;
    color: var(--ag-ink-3);
  }

  .delete-btn {
    width: 28px;
    height: 28px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 auto;
    border: 0.5px solid transparent;
    border-radius: 8px;
    background: transparent;
    color: var(--ag-ink-3);
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.12s ease, color 0.12s ease, background 0.12s ease;
  }

  .session-item:hover .delete-btn,
  .session-item:focus-within .delete-btn {
    opacity: 1;
  }

  .delete-btn:hover {
    color: var(--ag-warm);
    background: var(--ag-warm-light);
    border-color: rgba(201,124,74,0.25);
  }

  .settings-link {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 12px;
    color: var(--ag-ink-2);
    cursor: pointer;
    border: 0.5px solid transparent;
    transition: background 0.12s ease, border-color 0.12s ease;
  }

  .settings-link:hover {
    background: var(--ag-warm-white);
    border-color: var(--ag-border);
    color: var(--ag-ink);
  }

  .modal-overlay {
    position: fixed;
    inset: 0;
    z-index: 2000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    background: rgba(28,24,20,0.38);
    backdrop-filter: blur(8px);
  }

  .modal-content {
    width: min(420px, 100%);
    background: var(--ag-warm-white);
    border: 0.5px solid var(--ag-border);
    border-radius: 24px;
    padding: 22px;
    color: var(--ag-ink);
  }

  .modal-header {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .modal-icon {
    width: 36px;
    height: 36px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 12px;
    background: var(--ag-warm-light);
    color: var(--ag-warm);
    border: 0.5px solid rgba(201,124,74,0.25);
  }

  .modal-title {
    margin: 0;
    font-size: 20px;
    font-weight: 400;
    letter-spacing: -0.02em;
  }

  .modal-body {
    margin: 16px 0 0;
    color: var(--ag-ink-2);
    line-height: 1.6;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 24px;
  }

  .btn-cancel,
  .btn-delete {
    border-radius: 12px;
    padding: 8px 18px;
    font: inherit;
    font-weight: 500;
    cursor: pointer;
  }

  .btn-cancel {
    background: transparent;
    color: var(--ag-ink);
    border: 0.5px solid var(--ag-border);
  }

  .btn-cancel:hover {
    background: var(--ag-surface);
  }

  .btn-delete {
    background: var(--ag-warm-light);
    color: var(--ag-warm);
    border: 0.5px solid rgba(201,124,74,0.25);
  }

  @media (max-width: 820px) {
    .sidebar {
      width: 232px;
      padding: 18px 12px;
    }
  }
</style>
