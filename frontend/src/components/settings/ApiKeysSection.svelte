<script>
  import { onMount } from 'svelte';
  import { getApiKeys, deleteApiKey, updateApiKeyStatus } from '../../lib/api.js';
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
      <h2 class="section-title">API Keys Configuration</h2>
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
        Add Key
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
        <h3>No API Keys configured</h3>
        <p>Add your first API key to start using the intelligence engine.</p>
        <button class="btn-primary mt-4" onclick={() => showCreateModal = true}>
          Add Key
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
    title="Delete API Key"
    message="Are you sure you want to delete this API key? Outstanding requests might fail."
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
    font-weight: 600;
    color: var(--text-primary);
  }

  .section-description {
    margin: 0;
    font-size: 14px;
    color: var(--text-secondary);
  }

  .btn-primary {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 18px;
    border-radius: 8px;
    background: var(--accent-primary);
    color: var(--bg-base);
    font-weight: 600;
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
    border-radius: 8px;
    background: var(--surface-container-high);
    color: var(--text-primary);
    font-weight: 600;
    font-size: 14px;
    border: 1px solid var(--border-main);
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-secondary:hover {
    background: var(--border-main);
  }

  .btn-secondary:active {
    transform: translateY(0);
  }

  .btn-primary:hover {
    filter: brightness(1.1);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(217, 119, 87, 0.3);
  }

  .btn-primary:active {
    transform: translateY(0);
  }

  .error-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    background: var(--badge-err-bg);
    border: 1px solid var(--badge-err-border);
    border-radius: 8px;
    color: var(--status-err);
    font-size: 14px;
  }

  .btn-retry {
    margin-left: auto;
    background: none;
    border: 1px solid currentColor;
    color: inherit;
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
  }

  .btn-retry:hover {
    background: rgba(255,255,255,0.1);
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 64px 24px;
    background: var(--surface-container-high);
    border: 1px dashed var(--border-main);
    border-radius: 12px;
    text-align: center;
  }

  .empty-icon {
    width: 64px;
    height: 64px;
    border-radius: 16px;
    background: var(--glow-bg);
    color: var(--accent-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 24px;
  }

  .empty-state h3 {
    margin: 0 0 8px;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .empty-state p {
    margin: 0;
    font-size: 14px;
    color: var(--text-secondary);
    max-width: 300px;
  }

  .mt-4 { margin-top: 24px; }

  .loading-state {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 64px;
    color: var(--text-secondary);
    font-size: 14px;
  }

  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--border-main);
    border-top-color: var(--accent-primary);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
