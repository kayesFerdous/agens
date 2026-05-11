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
    background: var(--ag-cream);
  }

  .setup-panel {
    width: min(640px, 100%);
    border: 0.5px solid var(--ag-border);
    background: var(--ag-warm-white);
    border-radius: 24px;
    padding: 28px;
  }

  .setup-kicker {
    margin: 0 0 10px;
    color: var(--ag-accent);
    font-size: 0.8rem;
    font-weight: 500;
    letter-spacing: 0.01em;
  }

  h1 {
    margin: 0 0 12px;
    font-size: 1.75rem;
    line-height: 1.2;
    color: var(--ag-ink);
    letter-spacing: 0;
  }

  .setup-copy {
    margin: 0 0 22px;
    color: var(--ag-ink-2);
    line-height: 1.6;
  }

  .setup-cta {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: none;
    border-radius: 12px;
    background: var(--ag-ink);
    color: var(--ag-cream);
    cursor: pointer;
    font: inherit;
    font-size: 14px;
    font-weight: 500;
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
