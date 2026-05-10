<script>
  /**
   * MarkdownRenderer.svelte
   *
   * A reusable, streaming-safe Markdown renderer component.
   *
   * Props
   * ─────
   *   content {string}  — Markdown string. Can be updated incrementally (streaming).
   *   isLive  {boolean} — When true a blinking cursor is appended to signal
   *                       that the response is still being received.
   *
   * Usage
   * ─────
   *   <MarkdownRenderer content={response} isLive={streaming} />
   *
   * Streaming notes
   * ───────────────
   * Svelte's reactive `$:` re-runs renderMarkdownStream() every time `content`
   * changes. Because marked is synchronous and lightweight the update cycle is
   * imperceptible even at fast token rates (~30 ms/token).  The `{@html …}`
   * directive swaps only the inner DOM of .markdown-body, so the outer
   * component and sibling elements are never torn down → no flicker.
   */
  import { renderMarkdownStream } from '../lib/markdownUtils.js';

  export let content = '';
  export let isLive = false;

  $: htmlContent = renderMarkdownStream(content);
</script>

<div class="markdown-body">
  {@html htmlContent}
  {#if isLive}
    <span class="md-cursor" aria-hidden="true"></span>
  {/if}
</div>

<style>
  /* ── Reset / base ───────────────────────────────────────────────────── */
  .markdown-body {
    color: var(--text-primary, #e2e2e9);
    font-size: 14.5px;
    line-height: 1.85;
    word-break: break-word;
    font-family: 'Inter', system-ui, sans-serif;
  }

  /* ── Headings ───────────────────────────────────────────────────────── */
  .markdown-body :global(h1),
  .markdown-body :global(h2),
  .markdown-body :global(h3),
  .markdown-body :global(h4) {
    font-family: 'Inter', system-ui, sans-serif;
    font-weight: 600;
    color: var(--text-highlight, #f3f4f6);
    line-height: 1.35;
    margin: 1.4em 0 0.45em;
  }
  .markdown-body :global(h1) { font-size: 1.55em; letter-spacing: -0.02em; }
  .markdown-body :global(h2) { font-size: 1.25em; letter-spacing: -0.01em; }
  .markdown-body :global(h3) { font-size: 1.05em; }
  .markdown-body :global(h4) { font-size: 0.95em; text-transform: uppercase; letter-spacing: 0.05em; color: var(--accent-primary, #a78bfa); }

  /* First heading should not have extra top margin */
  .markdown-body :global(h1:first-child),
  .markdown-body :global(h2:first-child),
  .markdown-body :global(h3:first-child),
  .markdown-body :global(h4:first-child) {
    margin-top: 0;
  }

  /* ── Paragraphs ─────────────────────────────────────────────────────── */
  .markdown-body :global(p) {
    margin: 0 0 0.9em;
  }
  .markdown-body :global(p:last-child) {
    margin-bottom: 0;
  }

  /* ── Inline emphasis ────────────────────────────────────────────────── */
  .markdown-body :global(strong) {
    font-weight: 600;
    color: var(--text-highlight, #f3f4f6);
  }
  .markdown-body :global(em) {
    font-style: italic;
    color: var(--text-primary, #e2e2e9);
  }
  .markdown-body :global(del) {
    text-decoration: line-through;
    opacity: 0.55;
  }

  /* ── Links ──────────────────────────────────────────────────────────── */
  .markdown-body :global(a) {
    color: var(--accent-primary, #a78bfa);
    text-decoration: none;
    border-bottom: 1px solid transparent;
    transition: border-color 0.15s;
  }
  .markdown-body :global(a:hover) {
    border-bottom-color: var(--accent-primary, #a78bfa);
  }

  /* ── Lists ──────────────────────────────────────────────────────────── */
  .markdown-body :global(ul),
  .markdown-body :global(ol) {
    padding-left: 1.5em;
    margin: 0 0 0.9em;
  }
  .markdown-body :global(ul) {
    list-style-type: disc;
  }
  .markdown-body :global(ol) {
    list-style-type: decimal;
  }
  .markdown-body :global(li) {
    margin-bottom: 0.3em;
    padding-left: 0.25em;
  }
  .markdown-body :global(li::marker) {
    color: var(--accent-primary, #a78bfa);
  }
  /* Nested lists */
  .markdown-body :global(li > ul),
  .markdown-body :global(li > ol) {
    margin: 0.25em 0 0.25em;
  }

  /* ── Blockquote ─────────────────────────────────────────────────────── */
  .markdown-body :global(blockquote) {
    margin: 0.8em 0;
    padding: 0.6em 1em;
    border-left: 3px solid var(--accent-primary, #a78bfa);
    background: var(--surface-container-high, rgba(255,255,255,0.04));
    border-radius: 0 6px 6px 0;
    color: var(--text-secondary, #9ca3af);
    font-style: italic;
  }
  .markdown-body :global(blockquote p) {
    margin: 0;
  }

  /* ── Horizontal rule ────────────────────────────────────────────────── */
  .markdown-body :global(hr) {
    border: none;
    border-top: 1px solid var(--border-main, rgba(255,255,255,0.1));
    margin: 1.6em 0;
  }

  /* ── Inline code ────────────────────────────────────────────────────── */
  .markdown-body :global(code) {
    font-family: ui-monospace, 'Cascadia Code', 'Fira Code', Menlo, Consolas, monospace;
    font-size: 0.865em;
    background: var(--surface-container-high, rgba(255,255,255,0.08));
    color: var(--accent-primary, #a78bfa);
    padding: 0.17em 0.45em;
    border-radius: 5px;
    border: 1px solid var(--border-main, rgba(255,255,255,0.1));
  }

  /* ── Code blocks ────────────────────────────────────────────────────── */
  .markdown-body :global(pre) {
    background: var(--code-block-bg, #0f1117);
    border: 1px solid var(--border-main, rgba(255,255,255,0.1));
    border-radius: 10px;
    padding: 1em 1.25em;
    overflow-x: auto;
    margin: 0.9em 0;
    position: relative;
  }
  .markdown-body :global(pre code) {
    background: transparent;
    border: none;
    padding: 0;
    border-radius: 0;
    font-size: 0.875em;
    color: var(--code-text, #d4d4d8);
    line-height: 1.7;
  }

  /* Scrollbar inside code blocks */
  .markdown-body :global(pre::-webkit-scrollbar) {
    height: 5px;
  }
  .markdown-body :global(pre::-webkit-scrollbar-track) {
    background: transparent;
  }
  .markdown-body :global(pre::-webkit-scrollbar-thumb) {
    background: var(--border-main, rgba(255,255,255,0.2));
    border-radius: 3px;
  }

  /* ── Tables ─────────────────────────────────────────────────────────── */
  .markdown-body :global(table) {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9em;
    margin: 1em 0;
    border-radius: 8px;
    overflow: hidden;         /* clips the rounded corners on the wrapper */
    border: 1px solid var(--border-main, rgba(255,255,255,0.12));
  }
  .markdown-body :global(thead) {
    background: var(--surface-container-high, rgba(255,255,255,0.06));
  }
  .markdown-body :global(th) {
    font-weight: 600;
    font-size: 0.8em;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--text-highlight, #f3f4f6);
    padding: 9px 14px;
    text-align: left;
    border-bottom: 1px solid var(--border-main, rgba(255,255,255,0.12));
  }
  .markdown-body :global(td) {
    padding: 8px 14px;
    border-bottom: 1px solid var(--border-main, rgba(255,255,255,0.06));
    color: var(--text-primary, #e2e2e9);
    vertical-align: top;
  }
  /* Alternating row tint */
  .markdown-body :global(tbody tr:nth-child(even)) {
    background: var(--table-row-alt, rgba(255,255,255,0.025));
  }
  /* Remove bottom border on last row */
  .markdown-body :global(tbody tr:last-child td) {
    border-bottom: none;
  }
  /* Hover highlight */
  .markdown-body :global(tbody tr:hover) {
    background: var(--table-row-hover, rgba(167,139,250,0.07));
  }

  /* ── Images ─────────────────────────────────────────────────────────── */
  .markdown-body :global(img) {
    max-width: 100%;
    border-radius: 8px;
    display: block;
    margin: 0.75em 0;
  }

  /* ── Streaming cursor ────────────────────────────────────────────────── */
  .md-cursor {
    display: inline-block;
    width: 2px;
    height: 1.1em;
    background-color: var(--accent-primary, #a78bfa);
    vertical-align: text-bottom;
    margin-left: 2px;
    border-radius: 1px;
    animation: md-blink 0.9s ease-in-out infinite;
  }

  @keyframes md-blink {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0; }
  }
</style>
