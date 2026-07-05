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

const FUNCTION_LABELS: Record<string, string> = {
  translate_en2zh: "英译中",
  translate_zh2en: "中译英",
  summarize: "文本总结",
};

const STATUS_LABELS: Record<string, string> = {
  done: "完成",
  failed: "失败",
  running: "运行中",
  pending: "等待中",
  cancelled: "已取消",
};

function truncate(text: string, length = MAX_PREVIEW_LENGTH): string {
  if (!text) return "";
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABELS[status] ?? status}</span>;
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
      <Link to="/" className="back-link">
        ← 返回首页
      </Link>
      <div className="page-header">
        <span className="page-header-icon" aria-hidden="true">
          📊
        </span>
        <h1>历史记录</h1>
      </div>

      {error && <div className="empty-state">{error}</div>}
      {!error && records.length === 0 && <div className="empty-state">暂无记录，去试试翻译或总结吧</div>}
      {!error && records.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>功能</th>
                <th>状态</th>
                <th>耗时</th>
                <th>输入</th>
                <th>输出</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.id}>
                  <td className="cell-mono">{record.created_at}</td>
                  <td>{FUNCTION_LABELS[record.function_type] ?? record.function_type}</td>
                  <td>
                    <StatusBadge status={record.status} />
                  </td>
                  <td className="cell-mono">{record.duration_ms} ms</td>
                  <td title={record.input_text}>{truncate(record.input_text)}</td>
                  <td title={record.output_text}>{truncate(record.output_text)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
