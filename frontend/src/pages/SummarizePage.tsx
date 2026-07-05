import { useState } from "react";
import { Link } from "react-router-dom";
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
      <Link to="/" className="back-link">
        ← 返回首页
      </Link>
      <div className="page-header">
        <span className="page-header-icon" aria-hidden="true">
          📝
        </span>
        <h1>文本总结</h1>
      </div>

      <div className="field-row">
        <div>
          <label className="field-label" htmlFor="max-points-input">
            要点数
          </label>
          <input
            id="max-points-input"
            type="number"
            className="input input-number"
            min={1}
            max={10}
            value={maxPoints}
            onChange={(e) => setMaxPoints(Number(e.target.value))}
          />
        </div>
        <div>
          <span className="field-label">思考模式</span>
          <ModeToggle value={mode} onChange={setMode} />
        </div>
      </div>

      <div className="page-layout">
        <div className="card">
          <label className="field-label">原文</label>
          <VirtualTextarea value={text} onChange={setText} placeholder="粘贴长文本…" />
          <div className="btn-row">
            <button
              className="btn btn-primary"
              onClick={() => start("summarize", text, maxPoints, mode)}
              disabled={status === "running" || !text.trim()}
            >
              开始总结
            </button>
            <button className="btn btn-secondary" onClick={cancel} disabled={status !== "running"}>
              停止生成
            </button>
          </div>
        </div>

        <div className="card">
          <label className="field-label">总结结果</label>
          <StreamingOutput text={output} status={status} progressMessage={progressMessage} />
        </div>
      </div>
    </div>
  );
}
