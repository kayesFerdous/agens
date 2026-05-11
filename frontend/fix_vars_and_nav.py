import re
import os

# 1. Update app.css with proper variables
app_css = """@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&display=swap');

:root, :root[data-theme="light"] {
  --ag-cream: #F5F0E8;
  --ag-surface: #EEEAE1;
  --ag-warm-white: #FAF8F4;
  --ag-border: #D4CEBC;
  --ag-ink: #1C1814;
  --ag-ink-2: #4A4237;
  --ag-ink-3: #8C8070;
  --ag-accent: #7B6EAA;
  --ag-accent-mid: #A99DD1;
  --ag-accent-light: #EAE6F5;
  --ag-accent-deep: #5A4F8A;
  --ag-accent-glow: rgba(123,110,170,0.15);
  --ag-warm: #C97C4A;
  --ag-warm-light: #F5EAE0;
  --ag-border-focus: #7B6EAA;
  
  --font-sans: 'DM Sans', system-ui, -apple-system, sans-serif;
  --font-mono: ui-monospace, Consolas, monospace;
}

:root[data-theme="dark"] {
  --ag-cream: #0F0D0A;
  --ag-surface: #1A1713;
  --ag-warm-white: #1A1713;
  --ag-border: rgba(255,255,255,0.07);
  --ag-ink: rgba(245,240,232,0.85);
  --ag-ink-2: rgba(245,240,232,0.50);
  --ag-ink-3: rgba(245,240,232,0.30);
  --ag-accent: #7B6EAA;
  --ag-accent-mid: #A99DD1;
  --ag-accent-light: rgba(123,110,170,0.15);
  --ag-accent-deep: #5A4F8A;
  --ag-accent-glow: rgba(123,110,170,0.25);
  --ag-warm: #C97C4A;
  --ag-warm-light: rgba(201,124,74,0.15);
  --ag-border-focus: #A99DD1;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  padding: 0;
  background: var(--ag-cream);
  color: var(--ag-ink);
  font-family: var(--font-sans);
  font-weight: 400;
  font-size: 14px;
  line-height: 1.7;
}

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--ag-border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--ag-ink-3); }
"""
with open("/home/kayes/new_world/python/assistant/frontend/src/app.css", "w") as f:
    f.write(app_css)

# 2. Iterate through svelte files and replace hardcoded hexes with vars
color_map = {
    '#F5F0E8': 'var(--ag-cream)',
    '#EEEAE1': 'var(--ag-surface)',
    '#FAF8F4': 'var(--ag-warm-white)',
    '#D4CEBC': 'var(--ag-border)',
    '#1C1814': 'var(--ag-ink)',
    '#4A4237': 'var(--ag-ink-2)',
    '#8C8070': 'var(--ag-ink-3)',
    '#7B6EAA': 'var(--ag-accent)',
    '#A99DD1': 'var(--ag-accent-mid)',
    '#EAE6F5': 'var(--ag-accent-light)',
    '#5A4F8A': 'var(--ag-accent-deep)',
    'rgba(123,110,170,0.15)': 'var(--ag-accent-glow)',
    '#C97C4A': 'var(--ag-warm)',
    '#F5EAE0': 'var(--ag-warm-light)',
}

def replace_hex_with_vars(filepath):
    with open(filepath, 'r') as f:
        text = f.read()

    orig = text

    # Very specific replacement map based on exact codes we pumped in earlier
    for hex_val, var_name in color_map.items():
        text = text.replace(hex_val, var_name)

    # Replace exact transparent RGBA borders or backgrounds with variables where possible
    # We will just focus on the primary hexes that were hardcoded.
    
    # 3. specific Layout fix in App.svelte
    if filepath.endswith('App.svelte'):
        text = text.replace('width: 100vw;', 'width: 100%;')
        text = text.replace('height: 100vh;', 'height: 100vh;\n    overflow: hidden;')
        
        # Insert settings button between theme and cloud
        settings_btn = """
          <button class="icon-btn" aria-label="Settings" onclick={() => activePage.set('settings')}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
          </button>"""
        
        # Replace the <button class="icon-btn" aria-label="Cloud sync"> with settings
        cloud_btn_pattern = r'<button class="icon-btn" aria-label="Cloud sync">.*?</button>'
        text = re.sub(cloud_btn_pattern, settings_btn, text, flags=re.DOTALL)
        
    if filepath.endswith('Sidebar.svelte'):
        text = text.replace('left: 0;\n    top: 0;\n    width: 264px;\n    height: 100vh;', 'left: 0;\n    top: 0;\n    width: 264px;\n    height: 100vh;\n    box-sizing: border-box;')

    if orig != text:
        with open(filepath, 'w') as f:
            f.write(text)

for root, dirs, files in os.walk('/home/kayes/new_world/python/assistant/frontend/src'):
    for file in files:
        if file.endswith('.svelte'):
            replace_hex_with_vars(os.path.join(root, file))

