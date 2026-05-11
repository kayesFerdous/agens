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
    border-bottom: 0.5px solid var(--ag-border);
    margin-bottom: 24px;
  }

  .tab-btn {
    background: none;
    border: none;
    padding: 12px 16px;
    font-size: 14px;
    font-weight: 500;
    color: var(--ag-ink-2);
    cursor: pointer;
    position: relative;
    transition: color 0.2s;
  }

  .tab-btn:hover {
    color: var(--ag-ink);
  }

  .tab-btn.active {
    color: var(--ag-ink);
  }

  .tab-btn.active::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--ag-accent);
    border-radius: 2px 2px 0 0;
  }
</style>
