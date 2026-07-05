import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ModeToggle } from "../components/ModeToggle";
import { StreamingOutput } from "../components/StreamingOutput";
import { useSSETask } from "../hooks/useSSETask";

type Direction = "en2zh" | "zh2en";

export function TranslatePage() {
  const [searchParams] = useSearchParams();
  const [direction, setDirection] = useState<Direction>(
    (searchParams.get("direction") as Direction) ?? "en2zh"
  );
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"auto" | "fast" | "think">("auto");
  const { output, status, progressMessage, start, cancel } = useSSETask();

  const functionType = direction === "en2zh" ? "translate_en2zh" : "translate_zh2en";

  return (
    <div>
      <Link to="/" className="back-link">
        ← 返回首页
      </Link>
      <div className="page-header">
        <span className="page-header-icon" aria-hidden="true">
          🌐
        </span>
        <h1>翻译</h1>
      </div>

      <div className="field-row">
        <div>
          <label className="field-label" htmlFor="direction-select">
            翻译方向
          </label>
          <select
            id="direction-select"
            className="select"
            value={direction}
            onChange={(e) => setDirection(e.target.value as Direction)}
          >
            <option value="en2zh">英译中</option>
            <option value="zh2en">中译英</option>
          </select>
        </div>
        <div>
          <span className="field-label">思考模式</span>
          <ModeToggle value={mode} onChange={setMode} />
        </div>
      </div>

      <div className="page-layout">
        <div className="card">
          <label className="field-label" htmlFor="translate-input">
            原文
          </label>
          <textarea
            id="translate-input"
            className="textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            placeholder="输入要翻译的文本…"
          />
          <div className="btn-row">
            <button
              className="btn btn-primary"
              onClick={() => start(functionType, text, undefined, mode)}
              disabled={status === "running" || !text.trim()}
            >
              开始翻译
            </button>
            <button className="btn btn-secondary" onClick={cancel} disabled={status !== "running"}>
              停止生成
            </button>
          </div>
        </div>

        <div className="card">
          <label className="field-label">翻译结果</label>
          <StreamingOutput text={output} status={status} progressMessage={progressMessage} />
        </div>
      </div>
    </div>
  );
}
