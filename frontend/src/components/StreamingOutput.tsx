type Status = "idle" | "running" | "done" | "error" | "cancelled";

interface Props {
  text: string;
  status: Status;
  progressMessage?: string | null;
}

export function StreamingOutput({ text, status, progressMessage }: Props) {
  return (
    <div>
      {status === "running" && progressMessage && <div>{progressMessage}</div>}
      <pre data-testid="streaming-output">
        {text}
        {status === "running" && <span data-testid="cursor">▍</span>}
      </pre>
    </div>
  );
}
