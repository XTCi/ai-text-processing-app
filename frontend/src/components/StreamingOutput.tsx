type Status = "idle" | "running" | "done" | "error" | "cancelled";

interface Props {
  text: string;
  status: Status;
  progressMessage?: string | null;
}

const PLACEHOLDER = "结果将在这里流式显示…";

export function StreamingOutput({ text, status, progressMessage }: Props) {
  return (
    <div className="output-panel">
      {status === "running" && progressMessage && (
        <div className="output-progress">
          <span aria-hidden="true">⏳</span>
          {progressMessage}
        </div>
      )}
      <pre
        className="output-pre"
        data-testid="streaming-output"
        data-empty={text.length === 0}
        data-placeholder={PLACEHOLDER}
      >
        {text}
        {status === "running" && (
          <span className="output-cursor" data-testid="cursor">
            ▍
          </span>
        )}
      </pre>
    </div>
  );
}
