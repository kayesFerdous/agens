<script>
  import { onMount } from 'svelte';
  import { DEFAULT_TOOL_GROUPS, toolGroups } from '../lib/store.js';

  const GROUPS = [
    {
      id: 'filesystem',
      label: 'Filesystem',
      description: 'Files, search, and edits',
      icon: 'M4 6.5A2.5 2.5 0 0 1 6.5 4H10l2 2h5.5A2.5 2.5 0 0 1 20 8.5v7A2.5 2.5 0 0 1 17.5 18h-11A2.5 2.5 0 0 1 4 15.5z',
    },
    {
      id: 'scheduling',
      label: 'Scheduling',
      description: 'Events and agenda',
      icon: 'M7 3v3M17 3v3M4 9h16M6 5h12a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z',
    },
    {
      id: 'system',
      label: 'System',
      description: 'Shell and config',
      icon: 'M8 9l-4 3 4 3M16 9l4 3-4 3M14 5l-4 14',
    },
    {
      id: 'web',
      label: 'Web',
      description: 'Web search + full-page fetch',
      icon: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3.6 9h16.8M3.6 15h16.8M12 3c2.2 2.5 3.2 5.5 3.2 9S14.2 18.5 12 21c-2.2-2.5-3.2-5.5-3.2-9S9.8 5.5 12 3z',
    },
  ];

  let open = $state(false);
  let triggerRef = $state();
  let popoverRef = $state();

  let enabledCount = $derived(
    GROUPS.filter((group) => $toolGroups[group.id]).length
  );
  let allEnabled = $derived(enabledCount === GROUPS.length);

  function toggleOpen() {
    open = !open;
  }

  function setGroup(group, enabled) {
    toolGroups.update((current) => ({
      ...DEFAULT_TOOL_GROUPS,
      ...current,
      [group]: enabled,
    }));
  }

  function setAll(enabled) {
    toolGroups.set(
      Object.fromEntries(Object.keys(DEFAULT_TOOL_GROUPS).map((group) => [group, enabled]))
    );
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

  onMount(() => {
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  });
</script>

<div class="tool-selector">
  <button
    class="tool-trigger"
    class:open
    bind:this={triggerRef}
    type="button"
    onclick={toggleOpen}
    aria-haspopup="menu"
    aria-expanded={open}
    title="Active tool groups"
  >
    <span class="trigger-icon" aria-hidden="true">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 3l7 4v5c0 4.4-2.8 7.3-7 9-4.2-1.7-7-4.6-7-9V7z"></path>
        <path d="M9 12l2 2 4-5"></path>
      </svg>
    </span>
    <span class="trigger-text">Tools</span>
    <span class="trigger-count">{enabledCount}/{GROUPS.length}</span>
  </button>

  {#if open}
    <div class="popover" bind:this={popoverRef} role="menu">
      <div class="popover-header">
        <div>
          <p class="popover-title">Active tools</p>
          <p class="popover-subtitle">{enabledCount} of {GROUPS.length} enabled</p>
        </div>
        <button class="all-btn" type="button" onclick={() => setAll(!allEnabled)}>
          {allEnabled ? 'Disable all' : 'Enable all'}
        </button>
      </div>

      <div class="group-list">
        {#each GROUPS as group}
          {@const enabled = $toolGroups[group.id]}
          <label class="group-row" class:enabled>
            <input
              type="checkbox"
              checked={enabled}
              onchange={(event) => setGroup(group.id, event.target.checked)}
              aria-label={`${group.label} tools`}
            />
            <span class="row-icon" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
                <path d={group.icon}></path>
              </svg>
            </span>
            <span class="row-copy">
              <span class="row-title">{group.label}</span>
              <span class="row-description">{group.description}</span>
            </span>
            <span class="switch" aria-hidden="true">
              <span class="switch-thumb"></span>
            </span>
          </label>
        {/each}
      </div>
    </div>
  {/if}
</div>

<style>
  .tool-selector {
    position: relative;
    display: inline-flex;
    font-family: var(--font-sans);
  }

  .tool-trigger {
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

  .tool-trigger:hover,
  .tool-trigger.open {
    background: var(--ag-accent);
    border-color: var(--ag-accent);
    color: var(--ag-warm-white);
  }

  .tool-trigger:active {
    transform: translateY(1px);
  }

  .trigger-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
  }

  .trigger-count {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 28px;
    height: 18px;
    padding: 0 6px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.42);
    color: inherit;
    font-size: 10px;
    font-weight: 600;
  }

  .popover {
    position: absolute;
    left: 0;
    bottom: calc(100% + 10px);
    width: min(340px, calc(100vw - 32px));
    padding: 10px;
    border-radius: 18px;
    border: 0.5px solid color-mix(in srgb, var(--ag-border) 82%, var(--ag-accent));
    background: color-mix(in srgb, var(--ag-warm-white) 92%, white);
    box-shadow:
      0 22px 60px rgba(28, 24, 20, 0.12),
      0 4px 14px rgba(28, 24, 20, 0.08);
    z-index: 30;
  }

  .popover::after {
    content: "";
    position: absolute;
    left: 22px;
    bottom: -6px;
    width: 12px;
    height: 12px;
    background: inherit;
    border-right: 0.5px solid var(--ag-border);
    border-bottom: 0.5px solid var(--ag-border);
    transform: rotate(45deg);
  }

  .popover-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 6px 6px 10px;
    border-bottom: 0.5px solid var(--ag-border);
  }

  .popover-title,
  .popover-subtitle {
    margin: 0;
  }

  .popover-title {
    color: var(--ag-ink);
    font-size: 13px;
    font-weight: 600;
  }

  .popover-subtitle {
    color: var(--ag-ink-3);
    font-size: 11px;
  }

  .all-btn {
    border: 0.5px solid var(--ag-border);
    background: var(--ag-warm-white);
    color: var(--ag-ink-2);
    border-radius: 8px;
    padding: 6px 9px;
    font-family: inherit;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease;
  }

  .all-btn:hover {
    background: var(--ag-surface);
    color: var(--ag-ink);
  }

  .group-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding-top: 8px;
  }

  .group-row {
    display: grid;
    grid-template-columns: 32px 1fr 42px;
    align-items: center;
    gap: 10px;
    min-height: 54px;
    padding: 8px 8px;
    border-radius: 12px;
    border: 0.5px solid transparent;
    cursor: pointer;
    transition:
      background 0.15s ease,
      border-color 0.15s ease;
  }

  .group-row:hover,
  .group-row.enabled {
    background: color-mix(in srgb, var(--ag-accent-light) 40%, transparent);
    border-color: rgba(123, 110, 170, 0.14);
  }

  .group-row input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
  }

  .row-icon {
    width: 32px;
    height: 32px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    color: var(--ag-ink-3);
    background: var(--ag-surface);
    border: 0.5px solid var(--ag-border);
    transition:
      color 0.15s ease,
      background 0.15s ease,
      border-color 0.15s ease;
  }

  .group-row.enabled .row-icon {
    color: var(--ag-accent-deep);
    background: var(--ag-accent-light);
    border-color: rgba(123, 110, 170, 0.18);
  }

  .row-copy {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .row-title {
    color: var(--ag-ink);
    font-size: 13px;
    font-weight: 550;
    line-height: 1.2;
  }

  .row-description {
    color: var(--ag-ink-3);
    font-size: 11px;
    line-height: 1.3;
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .switch {
    position: relative;
    width: 38px;
    height: 22px;
    border-radius: 999px;
    background: var(--ag-surface);
    border: 0.5px solid var(--ag-border);
    box-sizing: border-box;
    transition:
      background 0.18s ease,
      border-color 0.18s ease;
  }

  .switch-thumb {
    position: absolute;
    top: 50%;
    left: 2.5px;
    width: 16px;
    height: 16px;
    border-radius: 999px;
    background: var(--ag-ink-3);
    transform: translateY(-50%);
    transition:
      transform 0.18s ease,
      background 0.18s ease;
  }

  .group-row.enabled .switch {
    background: var(--ag-accent);
    border-color: var(--ag-accent);
  }

  .group-row.enabled .switch-thumb {
    transform: translate(16px, -50%);
    background: var(--ag-warm-white);
  }

  @media (max-width: 560px) {
    .trigger-text {
      display: none;
    }

    .popover {
      left: -8px;
      width: min(328px, calc(100vw - 24px));
    }
  }
</style>
