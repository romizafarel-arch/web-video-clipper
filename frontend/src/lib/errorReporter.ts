/**
 * Helper to report frontend errors to Reef Flow via backend proxy.
 * Ensures non-blocking async execution without exposing API keys in browser client.
 */

export type ReefFlowPriority = 'URGENT' | 'HIGH' | 'MEDIUM' | 'LOW';

export async function reportErrorToReefFlow(
  title: string,
  description?: string,
  priority: ReefFlowPriority = 'HIGH'
): Promise<void> {
  try {
    const payload = {
      title: title.slice(0, 120),
      description: description || '',
      priority,
      status: 'TODO',
    };

    await fetch('/api/report-error', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }).catch(() => {});
  } catch {
    // Non-blocking & silent error handling
  }
}
