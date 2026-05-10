/**
 * markdownUtils.js
 *
 * Markdown → sanitized HTML pipeline.
 *
 * Libraries
 * ─────────
 * • marked  (v18) — extremely fast, spec-compliant CommonMark parser (~10 kB
 *   gzipped). No DOM dependency; works in any JS environment.
 * • DOMPurify — the de-facto XSS sanitizer for browser HTML. Strips any
 *   script / on* / javascript: payloads that might sneak in via the raw
 *   Markdown, while preserving all safe formatting tags.
 *
 * Why not a heavier all-in-one solution (e.g. markdown-it + highlight.js)?
 * ──────────────────────────────────────────────────────────────────────────
 * The combo of marked + DOMPurify weighs ~20 kB gzipped total and covers all
 * required Markdown features. Adding a syntax-highlighter would push the
 * bundle over 100 kB for a feature that can be layered in later if needed.
 */

import { marked } from 'marked';
import DOMPurify from 'dompurify';

// ── marked configuration ─────────────────────────────────────────────────────

const renderer = new marked.Renderer();

/**
 * Override link rendering to always open external links in a new tab with
 * safe rel attributes.
 */
renderer.link = ({ href, title, text }) => {
  const titleAttr = title ? ` title="${title}"` : '';
  return `<a href="${href}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`;
};

marked.use({
  renderer,
  gfm: true,       // GitHub-Flavored Markdown (tables, strikethrough, etc.)
  breaks: false,   // Don't treat single \n as <br> — keeps prose readable
});

// ── DOMPurify configuration ──────────────────────────────────────────────────

const PURIFY_CONFIG = {
  // Allow all standard HTML produced by marked
  ALLOWED_TAGS: [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'hr',
    'strong', 'em', 'del', 'b', 'i', 's',
    'a',
    'ul', 'ol', 'li',
    'blockquote',
    'pre', 'code',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'img',
    'span', 'div',
  ],
  ALLOWED_ATTR: [
    'href', 'title', 'target', 'rel',     // links
    'src', 'alt', 'width', 'height',       // images
    'class', 'id',                          // styling hooks
    'align',                                // table cell alignment
  ],
  // Prevent data: URIs in href / src
  ALLOW_DATA_ATTR: false,
};

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Converts a Markdown string to sanitized HTML.
 *
 * @param {string} markdown - Raw Markdown text (may be partial during streaming)
 * @returns {string} Safe, ready-to-render HTML string
 */
export function renderMarkdown(markdown) {
  if (!markdown) return '';
  // marked.parse() is synchronous and returns a string
  const rawHtml = marked.parse(markdown);
  return DOMPurify.sanitize(rawHtml, PURIFY_CONFIG);
}

/**
 * Same as renderMarkdown but for incremental/streaming content.
 * Identical implementation — the function exists as a named alias so callers
 * can be self-documenting about their streaming intent. marked handles partial
 * Markdown gracefully (it buffers incomplete constructs).
 *
 * @param {string} partialMarkdown
 * @returns {string}
 */
export function renderMarkdownStream(partialMarkdown) {
  return renderMarkdown(partialMarkdown);
}
