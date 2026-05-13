<script>
  import { onMount } from 'svelte';

  const DEFAULT_MODEL = 'gemini/gemini-2.5-flash-lite';
  const STORAGE_KEY = 'ai_selected_model';

  let { selectedModel = $bindable(DEFAULT_MODEL), onchange } = $props();

  const MODEL_GROUPS = [
    {
      provider: 'Gemini',
      prefix: 'gemini',
      models: [
        'gemini-3.1-pro-preview',
        'gemini-3.1-pro-preview-customtools',
        'gemini-3-flash-preview',
        // 'gemini-3.1-flash-lite-preview',
        'gemini-2.5-pro',
        'gemini-2.5-flash',
        'gemini-2.5-flash-lite',
      ]
    },
    {
      provider: 'Gemma',
      prefix: 'gemma',
      models: [
        'gemma-4-31b-it',
        'gemma-4-26b-a4b-it',
      ]
    }
  ];

  let open = $state(false);
  let triggerRef = $state();
  let dropdownRef = $state();

  let displayLabel = $derived(selectedModel.split('/')[1] ?? selectedModel);
  let providerLabel = $derived(selectedModel.split('/')[0] ?? '');

  function select(provider, model) {
    const value = `${provider}/${model}`;
    selectedModel = value;
    try { localStorage.setItem(STORAGE_KEY, value); } catch {}
    if (onchange) onchange(value);
    open = false;
  }

  function toggle() {
    open = !open;
  }

  function handleOutsideClick(e) {
    if (
      open &&
      triggerRef && !triggerRef.contains(e.target) &&
      dropdownRef && !dropdownRef.contains(e.target)
    ) {
      open = false;
    }
  }

  onMount(() => {
    // Restore persisted model selection
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        selectedModel = saved;
        if (onchange) onchange(saved);
      }
    } catch {}

    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  });
</script>

<div class="model-selector">
  <button
    class="trigger"
    class:open
    bind:this={triggerRef}
    onclick={toggle}
    aria-haspopup="listbox"
    aria-expanded={open}
    title="Select model"
  >
    <span class="provider-chip">{providerLabel}</span>
    <span class="model-name">{displayLabel}</span>
    <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="6 9 12 15 18 9"/>
    </svg>
  </button>

  {#if open}
    <div class="dropdown" bind:this={dropdownRef} role="listbox">
      {#each MODEL_GROUPS as group}
        <div class="group">
          <span class="group-header">{group.provider}</span>
          {#each group.models as model}
            {@const value = `${group.prefix}/${model}`}
            <button
              class="option"
              class:selected={selectedModel === value}
              role="option"
              aria-selected={selectedModel === value}
              onclick={() => select(group.prefix, model)}
            >
              <span class="option-provider">{group.prefix}/</span><span class="option-model">{model}</span>
              {#if selectedModel === value}
                <svg class="check" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              {/if}
            </button>
          {/each}
        </div>
      {/each}
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
    padding: 0 10px;
    border-radius: 9px;
    border: 0.5px solid rgba(123, 110, 170, 0.18);
    background: color-mix(in srgb, var(--ag-accent-light) 72%, var(--ag-warm-white));
    color: var(--ag-accent-deep);
    font-family: inherit;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    transition:
      background 0.15s ease,
      border-color 0.15s ease,
      color 0.15s ease,
      transform 0.15s ease;
    white-space: nowrap;
    user-select: none;
    box-sizing: border-box;
  }

  .trigger:hover,
  .trigger.open {
    background: var(--ag-accent);
    border-color: var(--ag-accent);
    color: var(--ag-warm-white);
  }

  .trigger:active {
    transform: translateY(1px);
  }

  .provider-chip {
    display: none; /* Combine text instead */
  }

  .model-name {
    font-size: inherit;
    font-weight: inherit;
    color: inherit;
    max-width: 160px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .chevron {
    opacity: 0.8;
    transition: transform 0.2s ease;
    flex-shrink: 0;
  }

  .trigger.open .chevron {
    transform: rotate(180deg);
  }

  /* Dropdown */
  .dropdown {
    position: absolute;
    bottom: calc(100% + 8px);
    left: 0;
    min-width: 250px;
    background: var(--ag-warm-white);
    border: 0.5px solid var(--ag-border);
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
    z-index: 100;
    overflow: hidden;
    animation: dropIn 0.15s ease;
    padding: 4px 0;
  }

  @keyframes dropIn {
    from {
      opacity: 0;
      transform: translateY(6px) scale(0.98);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  .group {
    padding: 4px 0;
  }

  .group + .group {
    border-top: 0.5px solid var(--ag-border);
  }

  .group-header {
    display: block;
    padding: 4px 14px;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.01em;
    color: var(--ag-ink-3);
  }

  .option {
    display: flex;
    align-items: center;
    width: 100%;
    padding: 8px 14px;
    border: none;
    background: none;
    text-align: left;
    font-family: inherit;
    font-size: 13px;
    cursor: pointer;
    transition: background 0.1s ease;
    color: var(--ag-ink-2);
    gap: 0;
  }

  .option:hover {
    background: rgba(60,50,30,0.05);
    color: var(--ag-ink);
  }

  .option.selected {
    background: rgba(123,110,170,0.05);
    color: var(--ag-accent);
  }

  .option-provider {
    color: var(--ag-ink-3);
    font-weight: 400;
    flex-shrink: 0;
  }

  .option-model {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 400;
  }

  .check {
    flex-shrink: 0;
    margin-left: 8px;
    color: var(--ag-accent);
  }

</style>
