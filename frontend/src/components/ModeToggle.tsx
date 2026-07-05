type Mode = "auto" | "fast" | "think";

interface Props {
  value: Mode;
  onChange: (mode: Mode) => void;
}

const OPTIONS: { mode: Mode; label: string }[] = [
  { mode: "auto", label: "自动" },
  { mode: "fast", label: "快速" },
  { mode: "think", label: "思考模式" },
];

export function ModeToggle({ value, onChange }: Props) {
  return (
    <div className="segmented" role="group" aria-label="模型模式">
      {OPTIONS.map(({ mode, label }) => (
        <button
          key={mode}
          type="button"
          className="segmented-option"
          data-testid={`mode-${mode}`}
          aria-pressed={value === mode}
          onClick={() => onChange(mode)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
