import sys

with open("frontend/src/components/ChatArea.svelte", "r") as f:
    content = f.read()

target = """.input-zone {
    flex-shrink: 0;
    max-width: 720px;
    width: 100%;
    margin: 0 auto;
    padding: 0 16px 24px;
    position: relative;
    z-index: 10;
  }"""

replacement = """.input-zone {
    flex-shrink: 0;
    max-width: 720px;
    width: 100%;
    margin: 0 auto;
    padding: 0 16px 24px;
    position: relative;
    z-index: 10;
    transition: transform 0.7s cubic-bezier(0.16, 1, 0.3, 1);
    transform: translateY(0);
  }

  .input-zone.is-centered {
    transform: translateY(calc(-50vh + 100px));
  }

  .hero-wrapper {
    position: absolute;
    top: -150px;
    left: 0;
    right: 0;
    display: flex;
    justify-content: center;
  }"""

content = content.replace(target, replacement)

with open("frontend/src/components/ChatArea.svelte", "w") as f:
    f.write(content)

