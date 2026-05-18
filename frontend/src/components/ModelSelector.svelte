<script>
  import { onMount, tick } from 'svelte';
  import { fetchModels, getWebPrefs, updateWebPrefs } from '../lib/api.js';
  import { activePage, settingsTab } from '../lib/store.js';
  import geminiLogo from '../assets/gemini.svg';
  import openaiLogo from '../assets/openai.svg';
  import groqLogo from '../assets/groq.svg';
  import cerebrasLogo from '../assets/cerebras.svg';
  import siliconflowLogo from '../assets/siliconcloud.svg';

  let { selectedModel = $bindable(null), onchange } = $props();

  let open = $state(false);
  let query = $state('');
  let loading = $state(false);
  let error = $state('');
  let catalog = $state({ providers: [] });
  let activeIndex = $state(0);
  let triggerRef = $state();
  let popoverRef = $state();
  let searchRef = $state();

  const providerLogos = {
    gemini: geminiLogo,
    openai: openaiLogo,
    groq: groqLogo,
    cerebras: cerebrasLogo,
    siliconflow: siliconflowLogo
  };

  const selectedInfo = $derived(findModel(selectedModel));
  const displayLabel = $derived(
    selectedInfo ? `${selectedInfo.provider.name} / ${selectedInfo.model.name}` : 'Auto'
  );

  const visibleProviders = $derived(filterProviders(catalog.providers, query));
  const selectableRows = $derived(buildSelectableRows(visibleProviders));

  function modelValue(provider, model) {
    return `${provider.id}/${model.id}`;
  }

  function findModel(value) {
    if (!value) return null;
    for (const provider of catalog.providers) {
      for (const model of provider.models) {
        if (modelValue(provider, model) === value) {
          return { provider, model };
        }
      }
    }
    return null;
  }

  function filterProviders(providers, value) {
    const needle = value.trim().toLowerCase();
    if (!needle) return providers;

    return providers
      .map((provider) => ({
        ...provider,
        models: provider.models.filter((model) => {
          return (
            model.name.toLowerCase().includes(needle) ||
            model.id.toLowerCase().includes(needle) ||
            provider.name.toLowerCase().includes(needle) ||
            model.speed_label.toLowerCase().includes(needle)
          );
        })
      }))
      .filter((provider) => provider.models.length > 0);
  }

  function buildSelectableRows(providers) {
    const rows = [{ type: 'auto', disabled: false }];
    for (const provider of providers) {
      for (const model of provider.models) {
        rows.push({
          type: 'model',
          provider,
          model,
          disabled: !provider.has_active_key || model.status === 'no_key'
        });
      }
    }
    return rows;
  }

  function openPopover() {
    open = true;
    activeIndex = Math.max(0, selectableRows.findIndex((row) => {
      if (row.type === 'auto') return selectedModel === null;
      return modelValue(row.provider, row.model) === selectedModel;
    }));
    tick().then(() => searchRef?.focus());
  }

  function toggle() {
    if (open) {
      open = false;
    } else {
      openPopover();
    }
  }

  function selectAuto() {
    selectedModel = null;
    if (onchange) onchange(null);
    updateWebPrefs({ selected_model: null }).catch(() => {});
    open = false;
  }

  function selectModel(provider, model) {
    if (!provider.has_active_key || model.status === 'no_key') return;
    const value = modelValue(provider, model);
    selectedModel = value;
    if (onchange) onchange(value);
    updateWebPrefs({ selected_model: value }).catch(() => {});
    open = false;
  }

  function goToApiKeys(event) {
    event.preventDefault();
    event.stopPropagation();
    settingsTab.set('apikeys');
    activePage.set('settings');
    open = false;
  }

  function formatCooldown(ts) {
    if (!ts) return '';
    return new Date(ts * 1000).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function moveActive(delta) {
    if (!selectableRows.length) return;
    let next = activeIndex;
    for (let i = 0; i < selectableRows.length; i += 1) {
      next = (next + delta + selectableRows.length) % selectableRows.length;
      if (!selectableRows[next].disabled) {
        activeIndex = next;
        return;
      }
    }
  }

  function selectActive() {
    const row = selectableRows[activeIndex];
    if (!row || row.disabled) return;
    if (row.type === 'auto') {
      selectAuto();
    } else {
      selectModel(row.provider, row.model);
    }
  }

  function handleKeydown(event) {
    if (!open) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      open = false;
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      moveActive(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      moveActive(-1);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      selectActive();
    } else if (event.key === '/' && document.activeElement !== searchRef) {
      event.preventDefault();
      searchRef?.focus();
    }
  }

  function handleOutsideClick(event) {
    if (
      open &&
      triggerRef && !triggerRef.contains(event.target) &&
      popoverRef && !popoverRef.contains(event.target)
    ) {
      open = false;
    }
  }

  async function loadModels() {
    loading = true;
    error = '';
    try {
      catalog = await fetchModels();
    } catch (err) {
      error = err.message || 'Could not load model list.';
    } finally {
      loading = false;
    }
  }

  async function loadPrefs() {
    try {
      const prefs = await getWebPrefs();
      selectedModel = prefs.selected_model || null;
      if (onchange) onchange(selectedModel);
    } catch {
      selectedModel = null;
    }
  }

  onMount(() => {
    loadModels();
    loadPrefs();
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  });
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="model-selector">
  <button
    class="trigger"
    class:open
    bind:this={triggerRef}
    onclick={toggle}
    aria-haspopup="listbox"
    aria-expanded={open}
    title="Select model"
    type="button"
  >
    <span class="sparkle">{selectedModel ? '' : '✦'}</span>
    <span class="model-name">{displayLabel}</span>
    <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="6 9 12 15 18 9"/>
    </svg>
  </button>

  {#if open}
    <div class="popover" bind:this={popoverRef} role="listbox">
      <div class="search-row">
        <span class="search-icon">⌕</span>
        <input
          bind:this={searchRef}
          bind:value={query}
          placeholder="Search models..."
          aria-label="Search models"
        />
        <span class="esc">esc</span>
      </div>

      {#if error}
        <div class="notice">{error}</div>
      {:else if loading}
        <div class="notice">Loading models...</div>
      {:else}
        <button
          class="auto-row"
          class:active={activeIndex === 0}
          class:selected={selectedModel === null}
          type="button"
          role="option"
          aria-selected={selectedModel === null}
          onclick={selectAuto}
        >
          <span class="indicator">{selectedModel === null ? '●' : '○'}</span>
          <span class="row-copy">
            <span class="row-title">✦ Auto (best available)</span>
            <span class="row-subtitle">Let Agens pick the fastest free model with an active key.</span>
          </span>
        </button>

        {#if visibleProviders.length === 0}
          <div class="notice">No models match your search.</div>
        {/if}

        {#each visibleProviders as provider}
          <section class="provider-group">
            <div
              class="provider-header"
              title={!provider.has_active_key ? `Add a ${provider.name} API key in Settings to enable these models.` : provider.name}
            >
              <span class="provider-heading">
                {#if providerLogos[provider.id]}
                  <img src={providerLogos[provider.id]} alt="" class="provider-logo" />
                {/if}
                <span>{provider.name}</span>
              </span>
              {#if !provider.has_active_key}
                <button class="add-key" type="button" onclick={goToApiKeys}>Add key →</button>
              {/if}
            </div>

            {#each provider.models as model}
              {@const value = modelValue(provider, model)}
              {@const disabled = !provider.has_active_key || model.status === 'no_key'}
              {@const rowIndex = selectableRows.findIndex((row) => row.type === 'model' && row.provider.id === provider.id && row.model.id === model.id)}
              <button
                class="model-row"
                class:active={activeIndex === rowIndex}
                class:selected={selectedModel === value}
                class:disabled
                type="button"
                role="option"
                aria-selected={selectedModel === value}
                aria-disabled={disabled}
                onclick={() => selectModel(provider, model)}
              >
                <span class="indicator">{selectedModel === value ? '●' : '○'}</span>
                <span class="row-copy">
                  <span class="row-title">
                    <span class="title-text">{model.name}</span>
                    {#if model.status === 'cooldown'}<span class="badge">⏳</span>{/if}
                    {#if model.free_tier}<span class="free-text">free</span>{/if}
                  </span>
                  <span class="row-subtitle">
                    {#if model.status === 'cooldown'}
                      Rate limited · available ~{formatCooldown(model.cooldown_until_ts)}
                    {:else if model.status === 'no_key'}
                      Add a {provider.name} key in Settings
                    {:else}
                      {model.speed_label} · {model.quota_label}
                    {/if}
                  </span>
                </span>
              </button>
            {/each}
          </section>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .model-selector {
    position: relative;
    display: inline-flex;
    font-family: var(--font-sans);
  }

  .trigger {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    height: 28px;
    max-width: 260px;
    padding: 0 10px;
    border-radius: 9px;
    border: 0.5px solid rgba(123, 110, 170, 0.25);
    background: var(--ag-accent-light);
    color: var(--ag-ink);
    font-family: inherit;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
    white-space: nowrap;
    user-select: none;
  }

  .trigger:hover,
  .trigger.open {
    background: var(--ag-accent);
    border-color: var(--ag-accent);
    color: var(--ag-warm-white);
  }

  .sparkle {
    width: 10px;
    color: inherit;
  }

  .model-name {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .chevron {
    flex-shrink: 0;
    opacity: 0.75;
    transition: transform 0.2s ease;
  }

  .trigger.open .chevron {
    transform: rotate(180deg);
  }

  .popover {
    position: absolute;
    bottom: calc(100% + 8px);
    left: 0;
    min-width: 320px;
    max-height: 400px;
    z-index: 50;
    overflow-y: auto;
    background: var(--ag-warm-white);
    border: 0.5px solid var(--ag-border);
    border-radius: 10px;
    box-shadow: 0 18px 60px rgba(0, 0, 0, 0.35);
  }

  .search-row {
    position: sticky;
    top: 0;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: var(--ag-warm-white);
    border-bottom: 0.5px solid var(--ag-border);
  }

  .search-icon,
  .esc {
    color: var(--ag-ink-3);
    font-size: 11px;
  }

  .search-row input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: transparent;
    color: var(--ag-ink);
    font-family: inherit;
    font-size: 13px;
  }

  .auto-row,
  .model-row {
    display: flex;
    width: 100%;
    gap: 9px;
    padding: 9px 12px;
    border: none;
    background: transparent;
    color: var(--ag-ink);
    font-family: inherit;
    text-align: left;
    cursor: pointer;
  }

  .auto-row {
    border-bottom: 0.5px solid var(--ag-border);
  }

  .auto-row:hover,
  .model-row:hover,
  .auto-row.active,
  .model-row.active {
    background: rgba(123, 110, 170, 0.14);
  }

  .auto-row.selected,
  .model-row.selected {
    color: var(--ag-accent-mid);
  }

  .model-row.disabled {
    opacity: 0.5;
    cursor: not-allowed;
    pointer-events: none;
  }

  .indicator {
    width: 14px;
    padding-top: 1px;
    color: var(--ag-accent-mid);
    flex-shrink: 0;
  }

  .row-copy {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 2px;
  }

  .row-title {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    min-width: 0;
    font-size: 13px;
    font-weight: 500;
    line-height: 1.25;
  }

  .title-text {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .badge,
  .free-text {
    flex-shrink: 0;
  }

  .badge {
    font-size: 12px;
  }

  .free-text {
    margin-left: auto;
    color: var(--ag-ink-3);
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    opacity: 0.65;
  }

  .row-subtitle {
    color: var(--ag-ink-3);
    font-size: 11px;
    line-height: 1.25;
  }

  .provider-group {
    border-bottom: 0.5px solid var(--ag-border);
  }

  .provider-group:last-child {
    border-bottom: none;
  }

  .provider-header {
    position: sticky;
    top: 41px;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 7px 12px;
    background: color-mix(in srgb, var(--ag-warm-white) 92%, var(--ag-surface));
    color: var(--ag-ink-2);
    font-size: 11px;
    font-weight: 600;
  }

  .provider-heading {
    display: inline-flex;
    align-items: center;
    min-width: 0;
    gap: 7px;
  }

  .provider-logo {
    width: 14px;
    height: 14px;
    object-fit: contain;
    color: currentColor;
    opacity: 0.9;
  }

  .add-key {
    border: none;
    background: transparent;
    color: var(--ag-accent-mid);
    cursor: pointer;
    font: inherit;
    padding: 0;
  }

  .add-key:hover {
    color: var(--ag-ink);
  }

  .notice {
    padding: 12px;
    color: var(--ag-ink-3);
    font-size: 12px;
  }
</style>
