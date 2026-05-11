<script>
  export let label;
  export let description;
</script>

<div class="setting-row">
  <div class="text-content">
    <div class="label">{label}</div>
    {#if description}
      <div class="description">{description}</div>
    {/if}
  </div>
  <div class="control">
    <slot />
  </div>
</div>

<style>
  .setting-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 0.5px solid var(--ag-border);
  }
  .setting-row:last-child {
    border-bottom: none;
  }
  .text-content {
    flex: 1;
    padding-right: 24px;
  }
  .label {
    font-size: 15px;
    font-weight: 500;
    color: var(--ag-ink);
    margin-bottom: 4px;
  }
  .description {
    font-size: 13px;
    color: var(--ag-ink-2);
    line-height: 1.4;
  }
  .control {
    flex-shrink: 0;
  }
</style>
