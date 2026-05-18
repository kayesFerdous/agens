<script>
  import { theme } from '../lib/store.js';
  
  import geminiLogo from '../assets/gemini.svg';
  import openaiLogo from '../assets/openai.svg';
  import openaiLogoDark from '../assets/openai-darkmode.svg';
  import groqLogo from '../assets/groq.svg';
  import groqLogoDark from '../assets/groq-darkmode.svg';
  import cerebrasLogo from '../assets/cerebras.svg';
  import cerebrasLogoDark from '../assets/cerebras-darkmode.svg';
  import siliconflowLogo from '../assets/siliconcloud.svg';

  let { provider = "", class: className = "" } = $props();

  const logosMap = $derived({
    gemini: geminiLogo,
    openai: $theme === 'dark' ? openaiLogoDark : openaiLogo,
    groq: $theme === 'dark' ? groqLogoDark : groqLogo,
    cerebras: $theme === 'dark' ? cerebrasLogoDark : cerebrasLogo,
    siliconflow: siliconflowLogo,
  });

  const logoUrl = $derived(logosMap[provider.toLowerCase()] || '');
</script>

{#if logoUrl}
  <img
    src={logoUrl}
    alt={provider}
    class="provider-logo {className}"
    onerror={(e) => { e.currentTarget.style.display='none'; e.currentTarget.nextElementSibling.style.display='flex'; }}
  />
{/if}
<div class="provider-logo-fallback {className}" style={logoUrl ? "display: none;" : ""}>
  {provider.charAt(0).toUpperCase()}
</div>

<style>
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
</style>
