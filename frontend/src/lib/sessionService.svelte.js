import { getSessions, deleteSession as apiDeleteSession } from './api.js';

class SessionService {
  sessions = $state([]);
  loading = $state(false);
  hasMore = $state(true);
  offset = $state(0);
  error = $state(null);
  LIMIT = 20;

  async loadInitial() {
    this.offset = 0;
    this.hasMore = true;
    this.sessions = [];
    await this.loadMore();
  }

  async loadMore() {
    if (this.loading || !this.hasMore) return;
    this.loading = true;
    this.error = null;
    try {
      const newSessions = await getSessions({ limit: this.LIMIT, offset: this.offset });
      if (newSessions.length < this.LIMIT) {
        this.hasMore = false;
      }
      this.sessions.push(...newSessions);
      this.offset += newSessions.length;
    } catch (err) {
      this.error = err.message;
      console.error('Failed to load sessions:', err);
    } finally {
      this.loading = false;
    }
  }

  async remove(id) {
    try {
      await apiDeleteSession(id);
      this.sessions = this.sessions.filter(s => s.id !== id);
      this.offset = Math.max(0, this.offset - 1);
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  }

  async refresh() {
    // Soft refresh to prepend new items
    try {
      const dbSessions = await getSessions({ limit: this.LIMIT, offset: 0 });
      this.sessions = dbSessions;
      this.offset = dbSessions.length;
      if (dbSessions.length < this.LIMIT) {
        this.hasMore = false;
      } else {
        this.hasMore = true;
      }
    } catch (err) {
      console.error("Failed to refresh sessions:", err);
    }
  }
}

export const sessionService = new SessionService();
