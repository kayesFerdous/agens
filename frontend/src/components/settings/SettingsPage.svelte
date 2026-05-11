<script>
  import TabNav from './TabNav.svelte';
  import GeneralSettings from './GeneralSettings.svelte';
  import ApiKeysSection from './ApiKeysSection.svelte';
  import { settingsTab } from '../../lib/store.js';

  const tabs = [
    { id: 'general', label: 'General' },
    { id: 'apikeys', label: 'API keys' }
  ];
  let activeTab = $state($settingsTab);
  let scrollContainer = $state();

  function handleTabChange(id) {
    activeTab = id;
    settingsTab.set(id);
  }

  $effect(() => {
    if ($settingsTab !== activeTab) {
      activeTab = $settingsTab;
    }
  });
</script>

<div class="settings-page" bind:this={scrollContainer}>
  <div class="page-header">
    <h1 class="page-title">Settings</h1>
  </div>
  
  <TabNav {tabs} {activeTab} onTabChange={handleTabChange} />

  <div class="tab-content">
    {#if activeTab === 'general'}
      <GeneralSettings />
    {:else if activeTab === 'apikeys'}
      <ApiKeysSection {scrollContainer} />
    {/if}
  </div>
</div>

<style>
  .settings-page {
    width: 100%;
    height: 100%;
    overflow-y: auto;
    padding: 32px 48px;
    background: var(--ag-cream);
    display: flex;
    flex-direction: column;
  }

  .settings-page > .page-header {
    margin-bottom: 24px;
  }

  .settings-page > .page-header .page-title {
    margin: 0;
    font-size: 24px;
    font-weight: 400;
    letter-spacing: -0.02em;
    color: var(--ag-ink);
  }

  .tab-content {
    flex: 1;
    animation: fadeIn 0.3s ease;
    max-width: 900px;
    margin: 0 auto;
    width: 100%;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
