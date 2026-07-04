import { useState } from "react";
import { ModeToggle } from "../components/ModeToggle";
import { StreamingOutput } from "../components/StreamingOutput";
import { VirtualTextarea } from "../components/VirtualTextarea";
import { useSSETask } from "../hooks/useSSETask";

export function SummarizePage() {
  const [text, setText] = useState("");
  const [maxPoints, setMaxPoints] = useState(3);
  const [mode, setMode] = useState<"auto" | "fast" | "think">("auto");
  const { output, status, progressMessage, start, cancel } = useSSETask();

  return (
    <div>
      <h1>文本总结</h1>
      <ModeToggle value={mode} onChange={setMode} />
      <div className="page-layout">
        <div>
          <VirtualTextarea value={text} onChange={setText} placeholder="粘贴长文本..." />
          <label>
            要点数
            <input
              type="number"
              min={1}
              max={10}
              value={maxPoints}
              onChange={(e) => setMaxPoints(Number(e.target.value))}
            />
          </label>
          <div>
            <button onClick={() => start("summarize", text, maxPoints, mode)} disabled={status === "running"}>
              开始总结
            </button>
            <button onClick={cancel} disabled={status !== "running"}>
              停止生成
            </button>
          </div>
        </div>
        <StreamingOutput text={output} status={status} progressMessage={progressMessage} />
      </div>
    </div>
  );
}
