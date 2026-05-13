<script>
  import { onMount } from "svelte";
  import SettingRow from "./SettingRow.svelte";
  import { getSettings, updateSettings } from "../../lib/api.js";

  let settings = $state({ safety_mode: true });
  let loading = $state(true);
  let error = $state(null);
  let saveStatus = $state(null); // null, 'saving', 'success', 'error'
  let saveTimeout = $state(null);

  async function loadSettings() {
    loading = true;
    error = null;
    try {
      const data = await getSettings();
      settings = data;
    } catch (err) {
      error = err.message || "Failed to load settings.";
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadSettings();
  });

  async function handleSafetyModeChange(event) {
    const newValue = event.target.checked;
    const oldValue = settings.safety_mode;

    // Optimistic UI update
    settings.safety_mode = newValue;
    saveStatus = "saving";

    try {
      await updateSettings({ safety_mode: newValue });
      saveStatus = "success";
      if (saveTimeout) clearTimeout(saveTimeout);
      saveTimeout = setTimeout(() => {
        saveStatus = null;
      }, 2000);
    } catch (err) {
      // Revert on error
      settings.safety_mode = oldValue;
      saveStatus = "error";
      console.error(err);
      if (saveTimeout) clearTimeout(saveTimeout);
      saveTimeout = setTimeout(() => {
        saveStatus = null;
      }, 3000);
    }
  }

</script>

<div class="general-settings">
  <div class="section-header">
    <h2>General preferences</h2>
    {#if saveStatus === "saving"}
      <span class="status-indicator">Saving...</span>
    {:else if saveStatus === "success"}
      <span class="status-indicator success">Saved</span>
    {:else if saveStatus === "error"}
      <span class="status-indicator error">Failed to save</span>
    {/if}
  </div>

  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <span>Loading settings...</span>
    </div>
  {:else if error}
    <div class="error-state">
      {error}
      <button class="btn-retry" onclick={loadSettings}>Retry</button>
    </div>
  {:else}
    <div class="settings-card">
      <SettingRow
        label="Safety mode"
        description="When enabled, the agent will ask for your confirmation before running any shell command."
      >
        <label class="safety-toggle" class:off={!settings.safety_mode}>
          <input
            type="checkbox"
            checked={settings.safety_mode}
            onchange={handleSafetyModeChange}
            aria-label="Safety mode"
          />
          <span class="toggle-track"></span>
          <span class="toggle-thumb"></span>
          <span class="toggle-label">{settings.safety_mode ? "On" : "Off"}</span
          >
        </label>
      </SettingRow>
    </div>
  {/if}
</div>

<style>
  .general-settings {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .section-header {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 500;
    color: var(--ag-ink);
  }

  .status-indicator {
    font-size: 12px;
    color: var(--ag-ink-2);
    transition: color 0.2s;
  }
  .status-indicator.success {
    color: var(--ag-accent);
  }
  .status-indicator.error {
    color: var(--ag-warm);
  }

  .settings-card {
    background: var(--ag-warm-white);
    border: 0.5px solid var(--ag-border);
    border-radius: 12px;
    overflow: hidden;
  }

  .loading-state,
  .error-state {
    padding: 32px;
    text-align: center;
    color: var(--ag-ink-2);
    font-size: 14px;
    background: var(--ag-warm-white);
    border-radius: 12px;
    border: 0.5px solid var(--ag-border);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
  }

  .error-state {
    color: var(--ag-warm);
  }

  .btn-retry {
    background: none;
    border: 0.5px solid var(--ag-border);
    color: inherit;
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.2s;
  }

  .btn-retry:hover {
    opacity: 0.8;
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid var(--ag-border);
    border-top-color: var(--ag-accent);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* Toggle Switch Styles */
  .safety-toggle {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    user-select: none;
  }

  .safety-toggle input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
  }

  .toggle-track {
    width: 46px;
    height: 26px;
    border-radius: 999px;
    background: rgba(217, 119, 87, 0.35);
    border: 0.5px solid var(--ag-border);
    transition:
      background 0.2s ease,
      border-color 0.2s ease;
  }

  .toggle-thumb {
    position: absolute;
    left: 4px;
    top: 4px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--ag-accent);
    transition: transform 0.2s ease;
  }

  .safety-toggle input:checked ~ .toggle-thumb {
    transform: translateX(20px);
  }

  .safety-toggle.off .toggle-track {
    background: var(--ag-warm-light);
    border-color: rgba(201,124,74,0.25);
  }

  .safety-toggle.off .toggle-label {
    color: var(--ag-warm);
  }

  .toggle-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--ag-ink-2);
    min-width: 28px;
    letter-spacing: 0.01em;
  }
</style>
