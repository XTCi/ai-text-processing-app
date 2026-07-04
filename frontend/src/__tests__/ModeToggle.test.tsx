import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ModeToggle } from "../components/ModeToggle";

describe("ModeToggle", () => {
  it("marks the current value as pressed", () => {
    render(<ModeToggle value="think" onChange={() => {}} />);
    expect(screen.getByTestId("mode-think")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("mode-fast")).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onChange with the clicked mode", async () => {
    const onChange = vi.fn();
    render(<ModeToggle value="auto" onChange={onChange} />);
    await userEvent.click(screen.getByTestId("mode-think"));
    expect(onChange).toHaveBeenCalledWith("think");
  });
});
