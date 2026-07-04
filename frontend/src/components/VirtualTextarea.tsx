import { useMemo } from "react";

const VIRTUALIZE_LINE_THRESHOLD = 500;
const VISIBLE_LINES = 40;

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function VirtualTextarea({ value, onChange, placeholder }: Props) {
  const lines = useMemo(() => value.split("\n"), [value]);
  const shouldVirtualize = lines.length >= VIRTUALIZE_LINE_THRESHOLD;

  return (
    <div>
      {shouldVirtualize && (
        <div
          data-testid="virtual-preview"
          style={{ maxHeight: `${VISIBLE_LINES * 1.4}em`, overflowY: "auto", opacity: 0.6 }}
        >
          {lines.slice(0, VISIBLE_LINES).join("\n")}
          {"\n… (" + (lines.length - VISIBLE_LINES) + " 行未显示，可直接在下方输入框继续编辑)"}
        </div>
      )}
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={shouldVirtualize ? 6 : 16}
        style={{ width: "100%" }}
      />
    </div>
  );
}
