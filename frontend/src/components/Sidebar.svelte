<script>
  import { activeSessionId, messages, activePage } from '../lib/store.js';
  import { sessionService } from '../lib/sessionService.svelte.js';
  import InfiniteScroll from './InfiniteScroll.svelte';

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

  function handleNewChat() {
    activeSessionId.set(null);
    messages.set([]);
    activePage.set('chat');
  }

  function selectSession(id) {
    activeSessionId.set(id);
    activePage.set('chat');
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

<aside class="sidebar">
  <div class="brand">
    <div class="brand-icon">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.9"/>
        <rect x="14" y="3" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.6"/>
        <rect x="3" y="14" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.6"/>
        <rect x="14" y="14" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.3"/>
      </svg>
    </div>
    <div>
      <h1 class="brand-name">The Intelligence Layer</h1>
      <p class="brand-version">V1.0.4 - STABLE</p>
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
    <p class="sessions-label">Recent Chats</p>
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

  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="settings-link" onclick={() => activePage.set('settings')}>
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <circle cx="12" cy="12" r="3"/>
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
    </svg>
    <span>Settings</span>
  </div>
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
        Are you sure you want to delete this conversation? This action cannot be undone.
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
    background: var(--bg-base);
    border-right: 1px solid var(--border-main);
    display: flex;
    flex-direction: column;
    padding: 24px 16px;
    gap: 32px;
    z-index: 50;
    font-family: 'Inter', sans-serif;
    -webkit-font-smoothing: antialiased;
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
    background: var(--glow-bg);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--accent-primary);
  }

  .brand-name {
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -0.04em;
    color: var(--text-primary);
    margin: 0;
  }

  .brand-version {
    font-size: 10px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.12em;
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
    background: var(--glow-bg);
    color: var(--accent-primary);
    font-weight: 600;
    font-size: 14px;
    border: none;
    cursor: pointer;
    transition: all 0.15s ease;
    font-family: inherit;
  }

  .new-chat-btn:hover {
    filter: brightness(1.1);
  }

  .new-chat-btn:active {
    transform: scale(0.98);
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
    font-weight: 700;
    color: var(--text-tertiary);
    padding: 0 8px 8px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin: 0;
  }

  .session-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border-radius: 4px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .session-item:hover {
    color: var(--text-primary);
    background: var(--surface-container-high);
  }

  .session-item.active {
    color: var(--accent-primary);
    font-weight: 600;
    border-left: 2px solid var(--accent-primary);
    background: var(--glow-bg);
  }

  .session-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    flex: 1;
  }

  .session-title {
    font-size: 13px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .session-time {
    font-size: 10px;
    color: var(--text-tertiary);
  }

  .delete-btn {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 4px;
    opacity: 0;
    transition: opacity 0.15s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
  }

  .session-item:hover .delete-btn {
    opacity: 0.5;
  }

  .delete-btn:hover {
    opacity: 1;
    color: var(--status-err);
  }

  .settings-link {
    margin-top: auto;
    padding-top: 24px;
    padding-bottom: 24px;
    border-top: 1px solid var(--border-main);
    display: flex;
    align-items: center;
    gap: 12px;
    padding-left: 12px;
    padding-right: 12px;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 14px;
    transition: color 0.2s ease;
  }

  .settings-link:hover {
    color: var(--text-primary);
  }

  .modal-overlay {
    position: fixed;
    inset: 0;
    z-index: 9999;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    animation: fadeIn 0.2s ease-out;
  }

  .modal-content {
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 16px;
    padding: 24px;
    width: 100%;
    max-width: 400px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    font-family: 'Inter', sans-serif;
  }

  .modal-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 12px;
  }

  .modal-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    background: var(--badge-err-bg); /* error-container soft */
    color: var(--status-err);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .modal-title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.01em;
  }

  .modal-body {
    margin: 0 0 32px;
    font-size: 14px;
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .modal-actions {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
  }

  .btn-cancel {
    padding: 10px 16px;
    border-radius: 8px;
    border: 1px solid var(--border-main);
    background: transparent;
    color: var(--text-primary);
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-cancel:hover {
    background: var(--surface-container-high);
  }

  .btn-delete {
    padding: 10px 16px;
    border-radius: 8px;
    border: 1px solid var(--badge-err-border);
    background: var(--badge-err-bg);
    color: var(--status-err);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-delete:hover {
    background: var(--badge-err-border);
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  @keyframes slideUp {
    from { opacity: 0; transform: translateY(16px) scale(0.96); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }
</style>
