import re

with open('src/components/MarkdownRenderer.svelte', 'r') as f:
    text = f.read()

# Replace legacy variable fallsbacks with new design system ones
text = text.replace("var(--text-primary, #e2e2e9)", "inherit")
text = text.replace("var(--text-highlight, #f3f4f6)", "inherit")
text = text.replace("font-family: 'Inter', system-ui, sans-serif;", "font-family: inherit;")
text = text.replace("var(--accent-primary, #a78bfa)", "#7B6EAA")
text = re.sub(r'font-weight: 600;', 'font-weight: 500;', text)

# For codeblocks and pre tags inside markdown
pattern_pre = r'\.markdown-body :global\(pre(?:(?!\n\}).)*?\n\}'
replacement_pre = """.markdown-body :global(pre) {
    background: #FAF8F4;
    border: 0.5px solid #D4CEBC;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 1em 0;
    overflow-x: auto;
    font-family: var(--font-mono);
  }"""
text = re.sub(r'\.markdown-body :global\(pre\).*?\n  \}', replacement_pre, text, flags=re.DOTALL)

with open('src/components/MarkdownRenderer.svelte', 'w') as f:
    f.write(text)

