<div class="hero-container">
  <h1 class="mark">agens</h1>
</div>

<style>
  .hero-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    pointer-events: none;
    position: relative;
    user-select: none;
  }
  
  .mark {
    font-size: 4rem;
    font-weight: 800; /* Bold, strong like KIMI */
    letter-spacing: 0.05em;
    margin: 0;
    color: var(--ag-ink);
  }

  @media (max-width: 640px) {
    .mark {
      font-size: 2.5rem;
    }
  }
</style>
