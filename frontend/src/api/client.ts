const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function submitTask(
  functionType: string,
  text: string,
  maxPoints?: number,
  mode: "auto" | "fast" | "think" = "auto"
): Promise<{ taskId: string }> {
  const resp = await fetch(`${API_BASE}/api/task`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ function_type: functionType, text, max_points: maxPoints ?? null, mode }),
  });
  if (!resp.ok) throw new Error(`submitTask failed: ${resp.status}`);
  const body = await resp.json();
  return { taskId: body.task_id };
}

export function streamUrl(taskId: string): string {
  return `${API_BASE}/api/task/${taskId}/stream`;
}

export async function cancelTask(taskId: string): Promise<void> {
  await fetch(`${API_BASE}/api/task/${taskId}`, { method: "DELETE" });
}
