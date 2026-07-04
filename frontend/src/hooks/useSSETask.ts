import { useCallback, useRef, useState } from "react";
import { cancelTask, streamUrl, submitTask } from "../api/client";
import { pollTaskUntilDone } from "./useTaskPolling";

type Status = "idle" | "running" | "done" | "error" | "cancelled";

export function useSSETask() {
  const [output, setOutput] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [stage, setStage] = useState<string | null>(null);
  const [progressMessage, setProgressMessage] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  const taskIdRef = useRef<string | null>(null);
  const bufferRef = useRef("");
  const pendingFlush = useRef(false);

  const flush = useCallback(() => {
    pendingFlush.current = false;
    const chunk = bufferRef.current;
    bufferRef.current = "";
    if (chunk) setOutput((prev) => prev + chunk);
  }, []);

  const scheduleFlush = useCallback(() => {
    if (pendingFlush.current) return;
    pendingFlush.current = true;
    requestAnimationFrame(flush);
  }, [flush]);

  const start = useCallback(
    async (functionType: string, text: string, maxPoints?: number, mode?: "auto" | "fast" | "think") => {
      setOutput("");
      bufferRef.current = "";
      setStatus("running");
      setStage(null);
      setProgressMessage(null);

      const { taskId } = await submitTask(functionType, text, maxPoints, mode);
      taskIdRef.current = taskId;
      const source = new EventSource(streamUrl(taskId));
      sourceRef.current = source;

      let errorCount = 0;
      let fallbackTriggered = false;
      source.onmessage = (ev) => {
        errorCount = 0;
        const event = JSON.parse(ev.data);
        if (event.type === "token") {
          setStage(event.stage ?? null);
          bufferRef.current += event.delta ?? "";
          scheduleFlush();
        } else if (event.type === "progress") {
          setStage(event.stage ?? null);
          setProgressMessage(event.message ?? null);
        } else if (event.type === "done") {
          flush();
          setStatus("done");
          source.close();
        } else if (event.type === "error") {
          flush();
          setStatus("error");
          source.close();
        } else if (event.type === "cancelled") {
          flush();
          setStatus("cancelled");
          source.close();
        }
      };
      source.onerror = () => {
        errorCount += 1;
        if (errorCount >= 3 && !fallbackTriggered) {
          fallbackTriggered = true;
          source.close();
          pollTaskUntilDone(taskId, (polledStatus, result) => {
            if (polledStatus === "done") {
              setOutput(result ?? "");
              setStatus("done");
            } else if (polledStatus === "failed") {
              setStatus("error");
            } else if (polledStatus === "cancelled") {
              setStatus("cancelled");
            }
          });
        }
      };
    },
    [flush, scheduleFlush]
  );

  const cancel = useCallback(() => {
    const taskId = taskIdRef.current;
    sourceRef.current?.close();
    setStatus("cancelled");
    if (taskId) void cancelTask(taskId);
  }, []);

  return { output, status, stage, progressMessage, start, cancel };
}
