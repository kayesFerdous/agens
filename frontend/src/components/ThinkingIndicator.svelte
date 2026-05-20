<div class="trace">
  <div class="trace-row">
    <div class="trace-left">
      <div class="ind think"></div>
      <span class="t-name">Planning...</span>
    </div>
  </div>
</div>

<style>
  .trace {
    display: flex;
    flex-direction: column;
    max-width: 480px;
    cursor: default;
    opacity: 0;
    transform: translateY(1px);
    animation: traceIn 0.2s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    position: relative;
    font-family: var(--font-sans);
    margin: 2px 0 4px 0;
  }

  .trace-row {
    display: flex;
    align-items: center;
    height: 22px;
    gap: 10px;
    padding: 3px 0;
  }

  .trace-left {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
    min-width: 0;
  }

  .ind {
    width: 5px;
    height: 5px;
    flex-shrink: 0;
    position: relative;
  }

  .ind.think {
    border: 1.5px solid var(--ag-accent);
    border-radius: 50%;
    box-sizing: border-box;
    animation: ringPulse 2.4s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  }

  @keyframes ringPulse {
    0%, 100% { opacity: 0.3; transform: scale(0.9); }
    50% { opacity: 1; transform: scale(1.1); }
  }

  .t-name {
    font-size: 11px;
    font-weight: 500;
    color: var(--ag-ink);
    letter-spacing: -0.01em;
    white-space: nowrap;
  }

  @keyframes traceIn {
    from { opacity: 0; transform: translateY(1px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
