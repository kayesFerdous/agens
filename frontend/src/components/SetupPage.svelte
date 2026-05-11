<script>
  import { activePage, settingsTab } from '../lib/store.js';

  function openApiKeys() {
    settingsTab.set('apikeys');
    activePage.set('settings');
  }
</script>

<div class="setup-page">
  <section class="setup-panel" aria-labelledby="setup-title">
    <p class="setup-kicker">Setup required</p>
    <h1 id="setup-title">No API keys configured yet</h1>
    <p class="setup-copy">
      Add an API key to start chatting with the local assistant. Chat stays unavailable until at least one active key exists.
    </p>
    <button type="button" class="setup-cta" onclick={openApiKeys}>
      Add your first API key
    </button>
  </section>
</div>

<style>
  .setup-page {
    width: 100%;
    min-height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 32px 16px;
    background: var(--bg-surface);
  }

  .setup-panel {
    width: min(640px, 100%);
    border: 1px solid var(--border-main);
    background: var(--surface-container-high);
    border-radius: 8px;
    padding: 28px;
    box-shadow: var(--shadow-input);
  }

  .setup-kicker {
    margin: 0 0 10px;
    color: var(--accent-primary);
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
  }

  h1 {
    margin: 0 0 12px;
    font-size: 1.75rem;
    line-height: 1.2;
    color: var(--text-primary);
    letter-spacing: 0;
  }

  .setup-copy {
    margin: 0 0 22px;
    color: var(--text-secondary);
    line-height: 1.6;
  }

  .setup-cta {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: none;
    border-radius: 8px;
    background: var(--accent-primary);
    color: #ffffff;
    cursor: pointer;
    font: inherit;
    font-size: 14px;
    font-weight: 700;
    padding: 11px 18px;
    transition: filter 0.2s ease, transform 0.2s ease;
  }

  .setup-cta:hover {
    filter: brightness(1.08);
    transform: translateY(-1px);
  }

  .setup-cta:active {
    transform: translateY(0);
  }
</style>
