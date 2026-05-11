<script>
  let { hasMore, loading, onloadmore } = $props();
  let observer;
  let sentinel;

  $effect(() => {
    if (observer) observer.disconnect();

    observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && hasMore && !loading) {
        onloadmore();
      }
    });

    if (sentinel) {
      observer.observe(sentinel);
    }

    return () => {
      if (observer) observer.disconnect();
    };
  });
</script>

<div bind:this={sentinel} class="sentinel">
  {#if loading}
    <div class="loading-indicator">
      <span>Loading...</span>
    </div>
  {/if}
</div>

<style>
  .sentinel {
    height: 32px;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 8px 0;
    margin-top: 4px;
    flex-shrink: 0;
  }
  .loading-indicator {
    font-size: 11px;
    color: var(--ag-ink-3);
    letter-spacing: 0.01em;
  }
</style>
