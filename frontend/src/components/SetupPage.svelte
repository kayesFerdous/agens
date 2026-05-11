<script>
  const command = 'vela apikey add <label> <provider> <key>';
  const example = 'vela apikey add personal gemini YOUR_API_KEY';
</script>

<div class="setup-page">
  <section class="setup-panel" aria-labelledby="setup-title">
    <p class="setup-kicker">Setup required</p>
    <h1 id="setup-title">No API keys found</h1>
    <p class="setup-copy">
      Vela needs at least one API key before chat can start. Add one from your
      terminal, then reload this page.
    </p>
    <div class="command-block">
      <span>Command</span>
      <code>{command}</code>
    </div>
    <div class="command-block muted">
      <span>Example</span>
      <code>{example}</code>
    </div>
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
  }

  .setup-panel {
    width: min(640px, 100%);
    border: 1px solid rgba(148, 163, 184, 0.24);
    background: rgba(17, 24, 39, 0.78);
    border-radius: 8px;
    padding: 28px;
  }

  .setup-kicker {
    margin: 0 0 10px;
    color: #f59e0b;
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

  .command-block {
    display: grid;
    gap: 8px;
    padding: 14px;
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 6px;
    background: rgba(2, 6, 23, 0.45);
    margin-top: 12px;
  }

  .command-block span {
    color: var(--text-secondary);
    font-size: 0.78rem;
    text-transform: uppercase;
    font-weight: 700;
  }

  .command-block code {
    color: #f8fafc;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .command-block.muted {
    background: transparent;
  }
</style>
