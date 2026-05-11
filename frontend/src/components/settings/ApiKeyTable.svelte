<script>
  export let keys = [];
  export let onDelete = (id) => {};
  export let onStatusChange = (id, status) => {};

  let openMenuId = null;

  function toggleMenu(id, e) {
    e.stopPropagation();
    openMenuId = openMenuId === id ? null : id;
  }

  function handleOutsideClick() {
    openMenuId = null;
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('click', handleOutsideClick);
  }

  function getStatusLabel(status) {
    if (status === 'rate_limited') return 'Rate limited';
    return status.charAt(0).toUpperCase() + status.slice(1);
  }

  function formatCooldown(untilIso) {
    if (!untilIso) return "Ready";
    const ms = Math.max(0, new Date(untilIso).getTime() - Date.now());
    if (ms <= 0) return "Ready";
    const secs = Math.ceil(ms / 1000);
    if (secs < 60) return `~${secs} sec`;
    const mins = Math.ceil(secs / 60);
    if (mins < 60) return `~${mins} min`;
    const hours = Math.floor(mins / 60);
    return `~${hours}h ${mins % 60}m`;
  }

  function getSortedModels(modelCooldowns) {
    if (!modelCooldowns) return [];
    return Object.entries(modelCooldowns).map(([model, cooldown]) => {
      return { model, ...cooldown };
    }).sort((a, b) => {
      const aActive = new Date(a.until).getTime() > Date.now();
      const bActive = new Date(b.until).getTime() > Date.now();
      if (aActive && !bActive) return -1;
      if (!aActive && bActive) return 1;
      return new Date(b.until).getTime() - new Date(a.until).getTime(); // longest cooldown first
    });
  }

  function formatDate(isoStr) {
    if (!isoStr) return 'Never';
    const msAgo = Date.now() - new Date(isoStr).getTime();
    if (msAgo < 60000) return 'Just now';
    const minsAgo = Math.floor(msAgo / 60000);
    if (minsAgo < 60) return `${minsAgo} min ago`;
    const hoursAgo = Math.floor(minsAgo / 60);
    if (hoursAgo < 24) return `${hoursAgo} hours ago`;
    return `${Math.floor(hoursAgo / 24)} days ago`;
  }
</script>

<div class="keys-list">
  {#each keys as key (key.id)}
    <div class="key-card">
      <div class="key-header">
        <div class="provider-info">
          <img src={`/src/assets/${key.provider.toLowerCase()}.svg`} alt={key.provider} class="provider-logo" onerror={(e) => { e.currentTarget.style.display='none'; e.currentTarget.nextElementSibling.style.display='flex'; }} />
          <div class="provider-logo-fallback" style="display: none;">{key.provider.charAt(0).toUpperCase()}</div>
          <span class="provider-name">{key.label ? `${key.label} — ${key.provider}` : key.provider}</span>
        </div>
        
        <code class="key-hint">{key.key_hint}</code>
        <span class="last-used">Last used: {formatDate(key.last_used_at)}</span>
        
        <div class="status-indicator status-{key.status}">
          <span class="status-dot"></span>
          {getStatusLabel(key.status)}
        </div>

        <div class="actions position-relative">
          <button class="action-btn" aria-label="Key actions" onclick={(e) => toggleMenu(key.id, e)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="1"></circle>
              <circle cx="12" cy="5" r="1"></circle>
              <circle cx="12" cy="19" r="1"></circle>
            </svg>
          </button>
          
          {#if openMenuId === key.id}
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div class="action-menu" onclick={(e) => e.stopPropagation()}>
              {#if key.status !== 'active'}
                <button onclick={() => { onStatusChange(key.id, 'active'); openMenuId = null; }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                  Activate
                </button>
              {/if}
              {#if key.status !== 'inactive'}
                <button onclick={() => { onStatusChange(key.id, 'inactive'); openMenuId = null; }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="9" x2="15" y2="15"></line><line x1="15" y1="9" x2="9" y2="15"></line></svg>
                  Deactivate
                </button>
              {/if}
              <div class="menu-divider"></div>
              <button class="text-danger" onclick={() => { onDelete(key.id); openMenuId = null; }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                Delete
              </button>
            </div>
          {/if}
        </div>
      </div>

      <div class="model-status-section">
        {#if !key.model_cooldowns || Object.keys(key.model_cooldowns).length === 0}
          <div class="all-ready">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            <span class="ready-text">All models ready</span>
          </div>
        {:else}
          <ul class="model-cooldown-list">
            {#each getSortedModels(key.model_cooldowns) as m}
              {@const cdText = formatCooldown(m.until)}
              <li class="model-row">
                <span class="model-name">{m.model}</span>
                <span class="divider">—</span>
                {#if cdText === 'Ready'}
                  <span class="model-ready">Ready</span>
                  <span class="dot-green"></span>
                {:else}
                  <span class="model-reason {m.reason === 'exhausted' ? 'reason-exhausted' : 'reason-rate'}">
                    {m.reason === 'exhausted' ? 'Exhausted' : 'Rate limited'}
                  </span>
                  <span class="dot-{m.reason === 'exhausted' ? 'red' : 'amber'}"></span>
                  <span class="cooldown-badge">{cdText}</span>
                {/if}
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </div>
  {/each}
</div>

<style>
  .keys-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .key-card {
    background: var(--ag-warm-white);
    border: 0.5px solid var(--ag-border);
    border-radius: 12px;
    overflow: visible;
    display: flex;
    flex-direction: column;
  }

  .key-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 0.5px solid var(--ag-border);
    gap: 16px;
  }

  .provider-info {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
    min-width: 0;
  }

  .provider-logo {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    object-fit: contain;
  }

  .provider-logo-fallback {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    background: var(--ag-accent-light);
    color: var(--ag-ink);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 500;
  }

  .provider-name {
    font-weight: 500;
    font-size: 15px;
    color: var(--ag-ink);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .key-hint {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--ag-ink-2);
    background: var(--ag-warm-white);
    padding: 4px 8px;
    border-radius: 4px;
    border: 0.5px solid var(--ag-border);
  }

  .last-used {
    font-size: 13px;
    color: var(--ag-ink-2);
    white-space: nowrap;
  }

  .status-indicator {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 500;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .status-active { color: var(--ag-accent); }
  .status-active .status-dot { background: var(--ag-accent); }
  
  .status-inactive { color: var(--ag-ink-2); }
  .status-inactive .status-dot { background: var(--ag-ink-3); }
  
  .status-rate_limited { color: var(--ag-warm); }
  .status-rate_limited .status-dot { background: var(--ag-warm); }

  .status-exhausted { color: var(--ag-warm); }
  .status-exhausted .status-dot { background: var(--ag-warm); }

  .status-invalid { color: var(--ag-warm); }
  .status-invalid .status-dot { background: var(--ag-warm); }

  .actions {
    display: flex;
    align-items: center;
    position: relative;
  }

  .action-btn {
    background: transparent;
    border: none;
    color: var(--ag-ink-2);
    cursor: pointer;
    padding: 6px;
    border-radius: 6px;
    display: flex;
    transition: all 0.2s;
  }

  .action-btn:hover {
    background: var(--ag-surface);
    color: var(--ag-ink);
  }

  .action-menu {
    position: absolute;
    right: 0;
    top: 36px;
    width: 160px;
    background: var(--ag-warm-white);
    border: 0.5px solid var(--ag-border);
    border-radius: 8px;
    box-shadow: none;
    z-index: 100;
    display: flex;
    flex-direction: column;
    padding: 6px;
  }

  .action-menu button {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    border-radius: 6px;
    color: var(--ag-ink);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
  }

  .action-menu button:hover {
    background: var(--ag-surface);
  }

  .action-menu button.text-danger {
    color: var(--ag-warm);
  }

  .action-menu button.text-danger:hover {
    background: var(--ag-warm-light);
  }

  .menu-divider {
    height: 0;
    background: var(--ag-border);
    margin: 4px 0;
  }

  .model-status-section {
    padding: 10px 20px;
    border-top: 0.5px solid var(--ag-border);
  }

  .all-ready {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--ag-accent);
    font-weight: 500;
  }

  .model-cooldown-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .model-row {
    display: flex;
    align-items: center;
    font-size: 13px;
    gap: 8px;
  }

  .model-name {
    color: var(--ag-ink);
    font-weight: 500;
  }

  .divider {
    color: var(--ag-ink-3);
  }

  .model-ready {
    color: var(--ag-accent);
  }

  .model-reason {
    font-weight: 500;
  }
  .reason-rate { color: var(--ag-warm); }
  .reason-exhausted { color: var(--ag-warm); }

  .dot-green, .dot-amber, .dot-red {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }
  .dot-green { background: var(--ag-accent); }
  .dot-amber { background: var(--ag-warm); }
  .dot-red { background: var(--ag-warm); }

  .cooldown-badge {
    background: var(--ag-warm-light);
    color: var(--ag-warm);
    border: 0.5px solid var(--ag-border);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
  }
</style>
