import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API_BASE } from "../api/client";

interface CallRecord {
  id: number;
  task_id: string;
  function_type: string;
  input_text: string;
  output_text: string;
  model_mode: string;
  status: string;
  duration_ms: number;
  created_at: string;
}

const MAX_PREVIEW_LENGTH = 40;

function truncate(text: string, length = MAX_PREVIEW_LENGTH): string {
  if (!text) return "";
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

export function RecordsPage() {
  const [records, setRecords] = useState<CallRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/records`)
      .then((r) => r.json())
      .then((body) => setRecords(body.records ?? []))
      .catch((err) => {
        console.error("failed to load records", err);
        setError("加载历史记录失败");
      });
  }, []);

  return (
    <div>
      <h1>历史记录</h1>
      <p>
        <Link to="/">返回首页</Link>
      </p>
      {error && <p>{error}</p>}
      {!error && records.length === 0 && <p>暂无记录</p>}
      {!error && records.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>功能类型</th>
              <th>状态</th>
              <th>耗时(ms)</th>
              <th>输入</th>
              <th>输出</th>
            </tr>
          </thead>
          <tbody>
            {records.map((record) => (
              <tr key={record.task_id}>
                <td>{record.created_at}</td>
                <td>{record.function_type}</td>
                <td>{record.status}</td>
                <td>{record.duration_ms}</td>
                <td title={record.input_text}>{truncate(record.input_text)}</td>
                <td title={record.output_text}>{truncate(record.output_text)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
