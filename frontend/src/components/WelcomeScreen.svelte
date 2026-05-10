<script>
  let { onsuggest } = $props();

  const chips = [
    {
      icon: 'search',
      title: 'Find all Python files',
      subtitle: 'Locate scripts across current project'
    },
    {
      icon: 'description',
      title: 'Summarize recent code',
      subtitle: 'Get a high-level view of changes'
    },
    {
      icon: 'terminal',
      title: 'Run a shell command',
      subtitle: 'Execute safe automated tasks'
    },
    {
      icon: 'bug_report',
      title: 'Analyze stack trace',
      subtitle: 'Debug the latest error logs'
    }
  ];

  function getSvgPath(icon) {
    switch(icon) {
      case 'search': return 'M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z';
      case 'description': return 'M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z';
      case 'terminal': return 'M20 4H4c-1.11 0-2 .9-2 2v12c0 1.1.89 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.89-2-2-2zm0 14H4V8h16v10zm-2-1h-6v-2h6v2zM7.5 17l-1.41-1.41L8.67 13l-2.58-2.59L7.5 9l4 4-4 4z';
      case 'bug_report': return 'M20 8h-2.81c-.45-.78-1.07-1.45-1.82-1.96L17 4.41 15.59 3l-2.17 2.17C12.96 5.06 12.49 5 12 5c-.49 0-.96.06-1.41.17L8.41 3 7 4.41l1.62 1.63C7.88 6.55 7.26 7.22 6.81 8H4v2h2.09c-.05.33-.09.66-.09 1v1H4v2h2v1c0 .34.04.67.09 1H4v2h2.81c1.04 1.79 2.97 3 5.19 3s4.15-1.21 5.19-3H20v-2h-2.09c.05-.33.09-.66.09-1v-1h2v-2h-2v-1c0-.34-.04-.67-.09-1H20V8zm-6 8h-4v-2h4v2zm0-4h-4v-2h4v2z';
      default: return '';
    }
  }

  function handleSuggest(text) {
    if (onsuggest) onsuggest(text);
  }
</script>

<div class="welcome-container">
  <div class="brand-moment">
    <div class="icon-box">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="currentColor">
        <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.36 8.04A5.994 5.994 0 0 0 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM19 18H6c-2.21 0-4-1.79-4-4 0-2.05 1.53-3.76 3.56-3.97l1.07-.11.5-.95C8.08 7.14 9.94 6 12 6c2.62 0 4.88 1.86 5.39 4.43l.3 1.5 1.53.11c1.56.1 2.78 1.41 2.78 2.96 0 1.65-1.35 3-3 3z"/>
      </svg>
    </div>
  </div>

  <h1 class="headline">How can I help you today?</h1>

  <div class="grid">
    {#each chips as chip}
      <button class="chip" onclick={() => handleSuggest(chip.title)}>
        <span class="chip-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d={getSvgPath(chip.icon)}/>
          </svg>
        </span>
        <div class="text-group">
          <div class="title">{chip.title}</div>
          <div class="subtitle">{chip.subtitle}</div>
        </div>
      </button>
    {/each}
  </div>
</div>

<style>
  .welcome-container {
    width: 100%;
    margin-bottom: 128px;
    display: flex;
    flex-direction: column;
    align-items: center;
    font-family: 'Inter', sans-serif;
  }

  .brand-moment {
    margin-bottom: 48px;
  }

  .icon-box {
    width: 64px;
    height: 64px;
    border-radius: 16px;
    background: linear-gradient(135deg, var(--primary), var(--primary-container));
    color: var(--on-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 20px 25px -5px rgba(192, 193, 255, 0.2);
  }

  .headline {
    font-size: 56px;
    font-weight: 700;
    line-height: 1.1;
    letter-spacing: -0.02em;
    color: var(--on-surface);
    text-align: center;
    margin: 0 0 32px 0;
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 12px;
    width: 100%;
  }

  @media (min-width: 768px) {
    .grid {
      grid-template-columns: 1fr 1fr;
    }
  }

  .chip {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    padding: 16px;
    border-radius: 12px;
    background: var(--surface-container-low);
    border: 1px solid rgba(72, 72, 72, 0.1); /* outline-variant */
    text-align: left;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .chip:hover {
    background: var(--surface-container-high);
    border-color: rgba(192, 193, 255, 0.3); /* primary */
  }

  .chip-icon {
    color: var(--primary);
    transition: transform 0.2s;
  }

  .chip:hover .chip-icon {
    transform: scale(1.1);
  }

  .text-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .title {
    font-size: 14px;
    font-weight: 600;
    color: var(--on-surface);
  }

  .subtitle {
    font-size: 12px;
    color: var(--on-surface-variant);
  }
</style>
