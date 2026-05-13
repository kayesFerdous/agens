<script>
  import logoUrl from '../assets/logo.svg';
  let { width = "100%", height = "100%", class: className = "" } = $props();
</script>

<img
  src={logoUrl}
  alt="App Logo"
  {width}
  {height}
  class={className}
/>

<style>
  img {
    object-fit: contain;
    flex-shrink: 0;
  }
</style>
