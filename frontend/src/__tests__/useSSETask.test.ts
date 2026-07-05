import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSSETask } from "../hooks/useSSETask";

class MockEventSource {
  static instances: MockEventSource[] = [];
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) {
    MockEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
  }
  emit(data: object) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ task_id: "t1", status: "pending" }) })
  );
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    cb(0);
    return 0;
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useSSETask", () => {
  it("streams tokens into output and marks done", async () => {
    const { result } = renderHook(() => useSSETask());

    await act(async () => {
      await result.current.start("translate_en2zh", "Hello");
    });

    const source = MockEventSource.instances[0];
    act(() => source.emit({ type: "token", stage: "draft", delta: "你" }));
    act(() => source.emit({ type: "token", stage: "draft", delta: "好" }));
    act(() => source.emit({ type: "done", result: "你好" }));

    await waitFor(() => expect(result.current.status).toBe("done"));
    expect(result.current.output).toBe("你好");
  });

  it("uses event.result as the authoritative output on done, not the accumulated tokens", async () => {
    // Mimics think-mode translate: Draft tokens stream, then Review tokens stream (a
    // different final answer), then a `done` event carries the final reviewed text.
    const { result } = renderHook(() => useSSETask());

    await act(async () => {
      await result.current.start("translate_en2zh", "Hello");
    });

    const source = MockEventSource.instances[0];
    act(() => source.emit({ type: "token", stage: "draft", delta: "你好" }));
    act(() => source.emit({ type: "token", stage: "review", delta: "你好呀" }));
    act(() => source.emit({ type: "done", result: "你好呀" }));

    await waitFor(() => expect(result.current.status).toBe("done"));
    // Accumulated tokens would have been "你好你好呀" (concatenated); the fix must
    // discard that in favor of the authoritative event.result.
    expect(result.current.output).toBe("你好呀");
  });

  it("renders a terminal-state-replay done event with no preceding tokens", async () => {
    // Mimics the SSE terminal-state-replay path for an already-completed task: only a
    // synthesized `done` event arrives, with `result` set and no `token` events at all.
    const { result } = renderHook(() => useSSETask());

    await act(async () => {
      await result.current.start("translate_en2zh", "Hello");
    });

    const source = MockEventSource.instances[0];
    act(() => source.emit({ type: "done", result: "已完成的翻译结果" }));

    await waitFor(() => expect(result.current.status).toBe("done"));
    expect(result.current.output).toBe("已完成的翻译结果");
  });

  it("surfaces progress messages", async () => {
    const { result } = renderHook(() => useSSETask());
    await act(async () => {
      await result.current.start("summarize", "长文本");
    });
    const source = MockEventSource.instances[0];
    act(() => source.emit({ type: "progress", stage: "chunk", message: "正在处理第 1/3 块" }));
    expect(result.current.progressMessage).toBe("正在处理第 1/3 块");
  });

  it("cancel closes the EventSource and sets status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === "DELETE") return Promise.resolve({ ok: true });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ task_id: "t1", status: "pending" }) });
    }));
    const { result } = renderHook(() => useSSETask());
    await act(async () => {
      await result.current.start("translate_en2zh", "Hello");
    });
    const source = MockEventSource.instances[0];

    act(() => result.current.cancel());

    expect(source.closed).toBe(true);
    expect(result.current.status).toBe("cancelled");
  });
});
