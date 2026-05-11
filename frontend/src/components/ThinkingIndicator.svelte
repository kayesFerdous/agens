<div class="thinking-row">
  <div class="t-pill">
    <div class="tdots"><span></span><span></span><span></span></div>
    thinking
  </div>
  <span class="t-hint">working…</span>
</div>

<style>
  .thinking-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 0;
    margin-bottom: 2px;
  }
  
  .t-pill {
    background: var(--ag-accent-light);
    border: 0.5px solid var(--ag-border);
    border-radius: 20px;
    padding: 3px 10px;
    font-family: var(--font-sans);
    font-size: 11px;
    color: var(--ag-accent);
    display: flex;
    align-items: center;
    gap: 5px;
  }
  
  .tdots span {
    width: 3px;
    height: 3px;
    border-radius: 50%;
    background: var(--ag-accent-mid);
    display: inline-block;
    animation: b 1.2s infinite;
  }
  
  .tdots span:nth-child(2) { animation-delay: .2s; }
  .tdots span:nth-child(3) { animation-delay: .4s; }
  
  @keyframes b {
    0%, 80%, 100% { opacity: .25; }
    40% { opacity: 1; }
  }
  
  .t-hint {
    font-size: 11px;
    color: var(--ag-ink-3);
    font-family: var(--font-sans);
  }
</style>
