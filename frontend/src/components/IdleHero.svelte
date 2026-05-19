<div class="hero-container">
  <h1 class="mark">AGENS</h1>
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
    font-size: 4.5rem;
    font-weight: 300;
    letter-spacing: 0.25em;
    margin: 0;
    margin-left: 0.25em; /* Optical centering for tracking */
    color: var(--ag-ink);
    opacity: 0;
    animation: simpleFadeIn 0.8s ease-out 0.1s forwards;
  }

  @keyframes simpleFadeIn {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (max-width: 640px) {
    .mark {
      font-size: 2.5rem;
    }
  }
</style>
