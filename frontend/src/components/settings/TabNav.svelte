<script>
  export let tabs = []; // [{ id: 'general', label: 'General' }, ...]
  export let activeTab = '';
  export let onTabChange = (id) => {};
</script>

<div class="tab-nav">
  {#each tabs as tab}
    <button 
      class="tab-btn" 
      class:active={activeTab === tab.id}
      onclick={() => onTabChange(tab.id)}
    >
      {tab.label}
    </button>
  {/each}
</div>

<style>
  .tab-nav {
    display: flex;
    gap: 8px;
    border-bottom: 1px solid var(--border-main);
    margin-bottom: 24px;
  }

  .tab-btn {
    background: none;
    border: none;
    padding: 12px 16px;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-secondary);
    cursor: pointer;
    position: relative;
    transition: color 0.2s;
  }

  .tab-btn:hover {
    color: var(--text-primary);
  }

  .tab-btn.active {
    color: var(--text-primary);
  }

  .tab-btn.active::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--accent-primary);
    border-radius: 2px 2px 0 0;
  }
</style>
