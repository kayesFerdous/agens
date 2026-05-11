<script>
  export let title = "Confirm action";
  export let message = "Are you sure you want to proceed?";
  export let confirmText = "Delete";
  export let cancelText = "Cancel";
  
  export let onConfirm = () => {};
  export let onCancel = () => {};

  // Handle escape key
  function handleKeydown(e) {
    if (e.key === 'Escape') onCancel();
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('keydown', handleKeydown);
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay" onclick={onCancel}>
  <div class="modal-content" onclick={(e) => e.stopPropagation()}>
    <div class="modal-header">
      <div class="modal-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 6h18"></path>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          <line x1="10" y1="11" x2="10" y2="17"></line>
          <line x1="14" y1="11" x2="14" y2="17"></line>
        </svg>
      </div>
      <h2 class="modal-title">{title}</h2>
    </div>
    <p class="modal-body">
      {message}
    </p>
    <div class="modal-actions">
      <button class="btn-cancel" onclick={onCancel}>{cancelText}</button>
      <button class="btn-danger" onclick={onConfirm}>{confirmText}</button>
    </div>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    z-index: 1000;
    background: rgba(28, 24, 20, 0.42);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    animation: fadeIn 0.2s ease-out;
  }

  .modal-content {
    background: var(--ag-warm-white);
    border: 0.5px solid var(--ag-border);
    border-radius: 24px;
    padding: 24px;
    width: 100%;
    max-width: 400px;
    box-shadow: none;
    animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .modal-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 12px;
  }

  .modal-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    background: var(--ag-warm-light);
    color: var(--ag-warm);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .modal-title {
    margin: 0;
    font-size: 18px;
    font-weight: 500;
    color: var(--ag-ink);
    letter-spacing: -0.01em;
  }

  .modal-body {
    margin: 0 0 32px;
    font-size: 14px;
    color: var(--ag-ink-2);
    line-height: 1.5;
  }

  .modal-actions {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
  }

  .btn-cancel {
    padding: 10px 16px;
    border-radius: 8px;
    border: 0.5px solid var(--ag-border);
    background: transparent;
    color: var(--ag-ink);
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-cancel:hover {
    background: var(--ag-surface);
  }

  .btn-danger {
    padding: 10px 16px;
    border-radius: 8px;
    border: 0.5px solid var(--ag-border);
    background: var(--ag-warm-light);
    color: var(--ag-warm);
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-danger:hover {
    background: var(--ag-surface);
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  @keyframes slideUp {
    from { opacity: 0; transform: translateY(16px) scale(0.96); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }
</style>
