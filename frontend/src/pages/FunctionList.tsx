import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

interface FunctionInfo {
  id: string;
  name: string;
  description: string;
}

const LINKS: Record<string, string> = {
  translate_en2zh: "/translate?direction=en2zh",
  translate_zh2en: "/translate?direction=zh2en",
  summarize: "/summarize",
};

export function FunctionList() {
  const [functions, setFunctions] = useState<FunctionInfo[]>([]);

  useEffect(() => {
    fetch("/api/functions")
      .then((r) => r.json())
      .then((body) => setFunctions(body.functions))
      .catch((err) => console.error("failed to load functions", err));
  }, []);

  return (
    <div>
      <h1>AI 文本处理</h1>
      <ul>
        {functions.map((f) => (
          <li key={f.id}>
            <Link to={LINKS[f.id] ?? "/"}>
              <strong>{f.name}</strong>
              <p>{f.description}</p>
            </Link>
          </li>
        ))}
      </ul>
      <p>
        <Link to="/records">查看历史记录</Link>
      </p>
    </div>
  );
}
