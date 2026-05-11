import re

with open('src/components/MarkdownRenderer.svelte', 'r') as f:
    text = f.read()

# Inline code
replacement_inline_code = """.markdown-body :global(code) {
    font-family: var(--font-mono);
    font-size: 0.85em;
    background: #FAF8F4;
    color: #4A4237;
    padding: 0.17em 0.45em;
    border-radius: 4px;
    border: 0.5px solid #D4CEBC;
  }"""
text = re.sub(r'\.markdown-body :global\(code\).*?\n  \}', replacement_inline_code, text, flags=re.DOTALL)

# Pre code
replacement_pre_code = """.markdown-body :global(pre code) {
    background: transparent;
    padding: 0;
    border-radius: 0;
    font-size: 13px;
    line-height: 1.6;
    color: #4A4237;
    border: none;
  }"""
text = re.sub(r'\.markdown-body :global\(pre code\).*?\n  \}', replacement_pre_code, text, flags=re.DOTALL)

with open('src/components/MarkdownRenderer.svelte', 'w') as f:
    f.write(text)

