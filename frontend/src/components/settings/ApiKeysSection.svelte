<script>
  import { onMount } from 'svelte';
  import { getApiKeys, deleteApiKey, updateApiKeyStatus } from '../../lib/api.js';
  import { noApiKeys } from '../../lib/store.js';
  import ApiKeyTable from './ApiKeyTable.svelte';
  import CreateApiKeyModal from './CreateApiKeyModal.svelte';
  import ConfirmActionModal from './ConfirmActionModal.svelte';

  let { scrollContainer } = $props();
  let keys = $state([]);
  let loading = $state(true);
  let error = $state(null);

  let showCreateModal = $state(false);
  let keyToDelete = $state(null);

  // Auto-scroll to bottom when keys list grows
  $effect(() => {
    if (scrollContainer && keys.length > 0) {
      // We use a small timeout to ensure DOM has rendered
      setTimeout(() => {
        scrollContainer.scrollTo({
          top: scrollContainer.scrollHeight,
          behavior: 'smooth'
        });
      }, 50);
    }
  });

  async function loadKeys() {
    loading = true;
    error = null;
    try {
      // By default no pagination mapping needed as API limits at 100 which is plenty for now
      keys = await getApiKeys();
      noApiKeys.set(!keys.some(key => key.status === 'active'));
    } catch (err) {
      error = err.message || 'Failed to load API keys.';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadKeys();
  });

  function handleKeyCreated() {
    showCreateModal = false;
    loadKeys();
  }

  function confirmDelete(keyId) {
    keyToDelete = keyId;
  }

  function cancelDelete() {
    keyToDelete = null;
  }

  async function executeDelete() {
    if (!keyToDelete) return;
    try {
      await deleteApiKey(keyToDelete);
      keys = keys.filter(k => k.id !== keyToDelete);
    } catch (err) {
      alert(err.message || 'Failed to delete key');
    } finally {
      keyToDelete = null;
    }
  }

  async function handleStatusChange(keyId, newStatus) {
    try {
      const updated = await updateApiKeyStatus(keyId, newStatus);
      keys = keys.map(k => k.id === keyId ? updated : k);
    } catch (err) {
      alert(err.message || 'Failed to update status');
    }
  }
</script>

<div class="api-keys-section">
  <div class="section-header">
    <div class="header-content">
      <h2 class="section-title">API keys</h2>
      <p class="section-description">Manage your API keys for different providers to power the local AI engine.</p>
    </div>
    <div class="header-actions">
      <button class="btn-secondary" onclick={loadKeys}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="23 4 23 10 17 10"></polyline>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
        </svg>
        Refresh
      </button>
      <button class="btn-primary" onclick={() => showCreateModal = true}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <line x1="12" y1="5" x2="12" y2="19"/>
          <line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        Add key
      </button>
    </div>
  </div>

  {#if error}
    <div class="error-banner">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <span>{error}</span>
      <button class="btn-retry" onclick={loadKeys}>Retry</button>
    </div>
  {/if}

  <div class="content">
    {#if loading}
      <div class="loading-state">
        <div class="spinner"></div>
        <span>Loading API keys...</span>
      </div>
    {:else if keys.length === 0}
      <div class="empty-state">
        <div class="empty-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
          </svg>
        </div>
        <h3>No API keys configured</h3>
        <p>Add your first API key to start using the intelligence engine.</p>
        <button class="btn-primary mt-4" onclick={() => showCreateModal = true}>
          Add key
        </button>
      </div>
    {:else}
      <ApiKeyTable 
        {keys} 
        onDelete={confirmDelete} 
        onStatusChange={handleStatusChange} 
      />
    {/if}
  </div>
</div>

{#if showCreateModal}
  <CreateApiKeyModal 
    onClose={() => showCreateModal = false} 
    onSuccess={handleKeyCreated} 
  />
{/if}

{#if keyToDelete}
  <ConfirmActionModal 
    title="Delete API key"
    message="Delete this API key? Outstanding requests might fail."
    onCancel={cancelDelete}
    onConfirm={executeDelete}
  />
{/if}

<style>
  .api-keys-section {
    display: flex;
    flex-direction: column;
    gap: 32px;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }

  .header-content {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .section-title {
    margin: 0;
    font-size: 18px;
    font-weight: 500;
    color: var(--ag-ink);
  }

  .section-description {
    margin: 0;
    font-size: 14px;
    color: var(--ag-ink-2);
  }

  .btn-primary {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 18px;
    border-radius: 12px;
    background: var(--ag-ink);
    color: var(--ag-cream);
    font-weight: 500;
    font-size: 14px;
    border: none;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .btn-secondary {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 18px;
    border-radius: 12px;
    background: transparent;
    color: var(--ag-ink);
    font-weight: 500;
    font-size: 14px;
    border: 0.5px solid var(--ag-border);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-secondary:hover {
    background: var(--ag-surface);
  }

  .btn-secondary:active {
    transform: translateY(0);
  }

  .btn-primary:hover {
    filter: brightness(1.1);
    transform: translateY(-1px);
    box-shadow: none;
  }

  .btn-primary:active {
    transform: translateY(0);
  }

  .error-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    background: var(--ag-warm-light);
    border: 0.5px solid var(--ag-border);
    border-radius: 12px;
    color: var(--ag-warm);
    font-size: 14px;
  }

  .btn-retry {
    margin-left: auto;
    background: none;
    border: 0.5px solid var(--ag-border);
    color: inherit;
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s;
  }

  .btn-retry:hover {
    background: var(--ag-warm-light);
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 64px 24px;
    background: var(--ag-warm-white);
    border: 0.5px dashed var(--ag-border);
    border-radius: 12px;
    text-align: center;
  }

  .empty-icon {
    width: 64px;
    height: 64px;
    border-radius: 16px;
    background: var(--ag-accent-light);
    color: var(--ag-accent);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 24px;
  }

  .empty-state h3 {
    margin: 0 0 8px;
    font-size: 18px;
    font-weight: 500;
    color: var(--ag-ink);
  }

  .empty-state p {
    margin: 0;
    font-size: 14px;
    color: var(--ag-ink-2);
    max-width: 300px;
  }

  .mt-4 { margin-top: 24px; }

  .loading-state {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 64px;
    color: var(--ag-ink-2);
    font-size: 14px;
  }

  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--ag-border);
    border-top-color: var(--ag-accent);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
