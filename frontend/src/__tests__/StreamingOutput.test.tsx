import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StreamingOutput } from "../components/StreamingOutput";

describe("StreamingOutput", () => {
  it("renders the accumulated text", () => {
    render(<StreamingOutput text="你好" status="running" />);
    expect(screen.getByTestId("streaming-output")).toHaveTextContent("你好");
  });

  it("shows a cursor while running and hides it when done", () => {
    const { rerender } = render(<StreamingOutput text="你好" status="running" />);
    expect(screen.getByTestId("cursor")).toBeInTheDocument();

    rerender(<StreamingOutput text="你好" status="done" />);
    expect(screen.queryByTestId("cursor")).not.toBeInTheDocument();
  });

  it("shows progress message only while running", () => {
    render(<StreamingOutput text="" status="running" progressMessage="正在处理第 1/3 块" />);
    expect(screen.getByText("正在处理第 1/3 块")).toBeInTheDocument();
  });
});
