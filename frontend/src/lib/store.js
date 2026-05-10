import { writable } from 'svelte/store';

export const activeSessionId = writable(null);
export const messages = writable([]);
export const isStreaming = writable(false);

/**
 * Set by App.svelte after loading a session whose last assistant message has
 * a tool_call with status "awaiting_user_confirmation".  ChatArea.svelte reads
 * this once on mount / reactive update and initialises its local
 * pendingConfirmation state, then clears the store.
 *
 * Shape: { preview: string, reason: string, requires_sudo_auth: boolean } | null
 */
export const restoredConfirmation = writable(null);
const initialPage = typeof window !== 'undefined'
  ? (new URLSearchParams(window.location.search).get('page') || 'chat')
  : 'chat';
export const activePage = writable(initialPage);

const storedTheme = typeof window !== 'undefined' ? localStorage.getItem('theme') : 'dark';
export const theme = writable(storedTheme || 'dark');
if (typeof window !== 'undefined') {
  theme.subscribe(val => {
    localStorage.setItem('theme', val);
    document.documentElement.setAttribute('data-theme', val);
  });
}
