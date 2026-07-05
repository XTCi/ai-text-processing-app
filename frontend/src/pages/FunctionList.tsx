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

const ICONS: Record<string, string> = {
  translate_en2zh: "🇬🇧→🇨🇳",
  translate_zh2en: "🇨🇳→🇬🇧",
  summarize: "📝",
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
      <div className="page-header">
        <h1>选择一个功能</h1>
        <span className="page-subtitle">流式输出 · 可随时取消 · 支持思考模式</span>
      </div>
      <ul className="card-grid">
        {functions.map((f) => (
          <li key={f.id}>
            <Link to={LINKS[f.id] ?? "/"} className="function-card">
              <span className="function-card-icon" aria-hidden="true">
                {ICONS[f.id] ?? "✨"}
              </span>
              <span className="function-card-title">{f.name}</span>
              <span className="function-card-desc">{f.description}</span>
            </Link>
          </li>
        ))}
      </ul>
      <Link to="/records" className="back-link">
        📊 查看历史记录
      </Link>
    </div>
  );
}
