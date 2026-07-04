import { useState } from "react";
import { useSearchParams } from "react-router-dom";
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
      <h1>翻译</h1>
      <select value={direction} onChange={(e) => setDirection(e.target.value as Direction)}>
        <option value="en2zh">英译中</option>
        <option value="zh2en">中译英</option>
      </select>
      <ModeToggle value={mode} onChange={setMode} />
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} style={{ width: "100%" }} />
      <div>
        <button onClick={() => start(functionType, text, undefined, mode)} disabled={status === "running"}>
          开始翻译
        </button>
        <button onClick={cancel} disabled={status !== "running"}>
          停止生成
        </button>
      </div>
      <StreamingOutput text={output} status={status} progressMessage={progressMessage} />
    </div>
  );
}
