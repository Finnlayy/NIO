import { useCallback, useEffect, useRef, useState } from "react";

/* ==================================================================== */
/* Dictation into the terminal input                                     */
/*                                                                       */
/* Audio is recorded in the tab and sent to `/api/apollo/transcribe`,     */
/* which talks to the local speech engine. The text lands in the input    */
/* and is never sent on its own: a misheard command must be readable      */
/* before it runs. Approvals are refused here: they stay typed.           */
/* ==================================================================== */

export const MAX_RECORDING_MS = 60_000;

const RECORDER_MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];

const ENGINE_OFFLINE = "speech engine is not running";

/** Spoken or typed forms of the approval commands. A voice never approves. */
const APPROVAL_COMMAND = /^\s*(\/|slash\s+)?(approve|deny)\b/i;

export type DictationState = "idle" | "recording" | "transcribing";
export type EngineState = "unknown" | "ready" | "offline";
export type SpeechStatus = "idle" | "listening" | "transcribing" | "offline";

export function speechStatus(state: DictationState, engine: EngineState): SpeechStatus {
  if (state === "recording") return "listening";
  if (state === "transcribing") return "transcribing";
  return engine === "offline" ? "offline" : "idle";
}

export function pickRecorderMime(isSupported: (mime: string) => boolean): string | undefined {
  return RECORDER_MIME_TYPES.find(isSupported);
}

export function appendTranscript(current: string, text: string): string {
  const addition = text.trim();
  if (!addition) return current;
  return current && !/\s$/.test(current) ? `${current} ${addition}` : `${current}${addition}`;
}

/** The input after a dictation, or `null` when the result would be an approval. */
export function joinDictation(current: string, text: string): string | null {
  const joined = appendTranscript(current, text);
  return APPROVAL_COMMAND.test(joined) ? null : joined;
}

export function microphoneError(error: unknown): string {
  const name = error instanceof Error ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") return "microphone blocked by the browser";
  if (name === "NotFoundError") return "no microphone found";
  if (name === "NotReadableError") return "microphone is in use by another app";
  return "microphone failed to start";
}

export async function transcribeAudio(audio: Blob): Promise<string> {
  const body = new FormData();
  body.set("file", audio, "dictation");
  const response = await fetch("/api/apollo/transcribe", { method: "POST", body });
  const result = (await response.json().catch(() => null)) as { ok?: boolean; text?: string; error?: string } | null;
  if (!response.ok || !result?.ok) {
    throw new Error(result?.error === "stt_unavailable" ? ENGINE_OFFLINE : "transcription failed");
  }
  return result.text ?? "";
}

export async function probeEngine(): Promise<EngineState> {
  try {
    const response = await fetch("/api/apollo/transcribe", { cache: "no-store" });
    return response.ok ? "ready" : "offline";
  } catch {
    return "unknown";
  }
}

export function useDictation(onText: (text: string) => void) {
  const [state, setState] = useState<DictationState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [engine, setEngine] = useState<EngineState>("unknown");

  const recorderRef = useRef<MediaRecorder | null>(null);
  const startingRef = useRef(false);
  const discardRef = useRef(false);
  const onTextRef = useRef(onText);
  useEffect(() => {
    onTextRef.current = onText;
  }, [onText]);

  const start = useCallback(async () => {
    if (startingRef.current) return;
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("this browser cannot record audio");
      return;
    }

    startingRef.current = true;
    discardRef.current = false;
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (cause) {
      setError(microphoneError(cause));
      return;
    } finally {
      startingRef.current = false;
    }
    if (discardRef.current) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }

    const mimeType = pickRecorderMime((mime) => MediaRecorder.isTypeSupported(mime));
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    const chunks: Blob[] = [];
    const limit = setTimeout(() => {
      if (recorder.state !== "inactive") recorder.stop();
    }, MAX_RECORDING_MS);

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = async () => {
      clearTimeout(limit);
      stream.getTracks().forEach((track) => track.stop());
      recorderRef.current = null;
      if (discardRef.current) {
        setState("idle");
        return;
      }
      setState("transcribing");
      try {
        const text = await transcribeAudio(new Blob(chunks, { type: recorder.mimeType }));
        setEngine("ready");
        if (discardRef.current) return;
        if (text) onTextRef.current(text);
        else setError("no speech recognized");
      } catch (cause) {
        const message = cause instanceof Error ? cause.message : "transcription failed";
        if (message === ENGINE_OFFLINE) setEngine("offline");
        if (!discardRef.current) setError(message);
      } finally {
        setState("idle");
      }
    };

    recorderRef.current = recorder;
    recorder.start();
    setState("recording");
  }, []);

  const toggle = useCallback(() => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    else if (state === "idle") void start();
  }, [start, state]);

  /** Drop whatever is in progress: no text reaches the input afterwards. */
  const cancel = useCallback(() => {
    discardRef.current = true;
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }, []);

  const probe = useCallback(async () => setEngine(await probeEngine()), []);
  const clearError = useCallback(() => setError(null), []);

  useEffect(() => cancel, [cancel]);

  return { state, error, speech: speechStatus(state, engine), toggle, cancel, probe, clearError, reject: setError };
}
