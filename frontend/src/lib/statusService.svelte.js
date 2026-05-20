class StatusService {
  isServerActive = $state(false);
  eventSource = null;

  connect() {
    if (this.eventSource || typeof window === 'undefined') return;

    const source = new EventSource('/api/status/stream');
    this.eventSource = source;

    source.onopen = () => {
      this.isServerActive = true;
    };

    source.onmessage = () => {
      this.isServerActive = true;
    };

    source.onerror = () => {
      this.isServerActive = false;
    };
  }

  disconnect() {
    if (!this.eventSource) return;
    this.eventSource.close();
    this.eventSource = null;
    this.isServerActive = false;
  }
}

export const statusService = new StatusService();
