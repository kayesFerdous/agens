import sys

with open("frontend/src/components/ChatArea.svelte", "r") as f:
    content = f.read()

target = """  <!-- The input and hero are wrapped together structurally when idle -->
  <div class="input-zone" class:is-centered={isIdle}>
    {#if isIdle}
       <div class="hero-wrapper">
         <IdleHero />
       </div>
    {/if}
    <div class="input-wrapper">
      <ChatInput
        onsuggest={handleSuggest}"""

replacement = """  <!-- The input and hero are wrapped together structurally when idle -->
  <div class="input-zone" class:is-centered={isIdle}>
    {#if isIdle}
       <div class="hero-wrapper">
         <IdleHero />
       </div>
    {/if}
    <div class="input-wrapper">
      <ChatInput"""

content = content.replace(target, replacement)

with open("frontend/src/components/ChatArea.svelte", "w") as f:
    f.write(content)

