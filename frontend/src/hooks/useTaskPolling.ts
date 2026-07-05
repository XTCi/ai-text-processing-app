import { API_BASE } from "../api/client";

async function fetchStatus(taskId: string): Promise<{ status: string; result?: string }> {
  const resp = await fetch(`${API_BASE}/api/task/${taskId}`);
  return resp.json();
}

export function pollTaskUntilDone(
  taskId: string,
  onUpdate: (status: string, result?: string) => void,
  intervalMs = 1000
): () => void {
  let stopped = false;

  const tick = async () => {
    if (stopped) return;
    const { status, result } = await fetchStatus(taskId);
    onUpdate(status, result);
    if (!stopped && !["done", "failed", "cancelled"].includes(status)) {
      setTimeout(tick, intervalMs);
    }
  };
  tick();

  return () => {
    stopped = true;
  };
}
