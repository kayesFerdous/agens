export const statusState = $state({ isServerActive: false });

class StatusService {
  eventSource = null;

  connect() {
    if (this.eventSource || typeof window === 'undefined') return;

    const source = new EventSource('/api/status/stream');
    this.eventSource = source;

    source.onopen = () => {
      statusState.isServerActive = true;
    };

    source.onmessage = () => {
      statusState.isServerActive = true;
    };

    source.onerror = () => {
      statusState.isServerActive = false;
    };
  }

  disconnect() {
    if (!this.eventSource) return;
    this.eventSource.close();
    this.eventSource = null;
    statusState.isServerActive = false;
  }
}

export const statusService = new StatusService();
