import { useCallback, useEffect, useRef, useState } from "react";
import { browserRecognition, startBrowserDictation } from "./browserSpeech";
import { COMMANDS } from "./commands";

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

/** Normalize only an explicit spoken slash followed by a known CLI command. */
export function normalizeDictation(text: string): string {
  const match = /^\s*(?:slash|schrägstrich)\s+([a-z]+)\b([\s\S]*)$/i.exec(text);
  if (!match || !COMMANDS.some(({ command }) => command === `/${match[1].toLowerCase()}`)) return text;
  return `/${match[1].toLowerCase()}${match[2]}`;
}

/** The input after a dictation, or `null` when the result would be an approval. */
export function joinDictation(current: string, text: string): string | null {
  const joined = appendTranscript(current, normalizeDictation(text));
  return APPROVAL_COMMAND.test(joined) ? null : joined;
}

export function microphoneError(error: unknown): string {
  const name = error instanceof Error ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") return "Microphone blocked by the browser. Open the preview in a new tab and allow microphone access in site settings.";
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

  const [mode, setMode] = useState<"local" | "browser">("local");
  const [language, setLanguage] = useState("en-US");
  const [browserSupported, setBrowserSupported] = useState(false);
  useEffect(() => setBrowserSupported(!!browserRecognition()), []);
  const browserSessionRef = useRef<ReturnType<typeof startBrowserDictation> | null>(null);
  const sessionRef = useRef(0);
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
    const session = ++sessionRef.current;
    if (mode === "browser") {
      const Recognition = browserRecognition();
      if (!Recognition) {
        setError("Browser speech is not supported here. Try Chrome or Edge, or configure the local speech engine.");
        return;
      }
      setState("recording");
      try {
        browserSessionRef.current = startBrowserDictation(Recognition, language, {
          onText: (text) => { if (session === sessionRef.current) onTextRef.current(text); },
          onError: (message) => { if (session === sessionRef.current) setError(message); },
          onEnd: () => {
            if (session !== sessionRef.current) return;
            browserSessionRef.current = null;
            setState("idle");
          },
        }, MAX_RECORDING_MS);
      } catch (cause) {
        setState("idle");
        setError(microphoneError(cause));
      }
      return;
    }
    if (engine === "offline") {
      setError(browserSupported
        ? "Local speech engine is offline. Select Browser speech below to dictate without it."
        : "Local speech engine is offline. Configure STT_ENDPOINT_URL, or use Chrome/Edge for browser speech.");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("this browser cannot record audio");
      return;
    }

    startingRef.current = true;
    discardRef.current = false;
    setState("recording");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (cause) {
      if (session === sessionRef.current) {
        setError(microphoneError(cause));
        setState("idle");
      }
      return;
    } finally {
      startingRef.current = false;
    }
    if (discardRef.current || session !== sessionRef.current) {
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
      if (discardRef.current || session !== sessionRef.current) {
        if (session === sessionRef.current) setState("idle");
        return;
      }
      setState("transcribing");
      try {
        const text = await transcribeAudio(new Blob(chunks, { type: recorder.mimeType }));
        if (discardRef.current || session !== sessionRef.current) return;
        setEngine("ready");
        if (text) onTextRef.current(text);
        else setError("no speech recognized");
      } catch (cause) {
        const message = cause instanceof Error ? cause.message : "transcription failed";
        if (message === ENGINE_OFFLINE) setEngine("offline");
        if (!discardRef.current && session === sessionRef.current) setError(message);
      } finally {
        if (session === sessionRef.current) setState("idle");
      }
    };

    recorderRef.current = recorder;
    recorder.start();
    setState("recording");
  }, [mode, language, engine, browserSupported]);

  const toggle = useCallback(() => {
    if (browserSessionRef.current) browserSessionRef.current.stop();
    else if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    else if (state === "idle") void start();
  }, [start, state]);

  /** Drop whatever is in progress: no text reaches the input afterwards. */
  const cancel = useCallback(() => {
    discardRef.current = true;
    sessionRef.current++;
    browserSessionRef.current?.cancel();
    browserSessionRef.current = null;
    setState("idle");
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }, []);

  const probe = useCallback(async () => setEngine(await probeEngine()), []);
  const clearError = useCallback(() => setError(null), []);

  useEffect(() => cancel, [cancel]);

  return {
    state, error, engine, mode, setMode, language, setLanguage, browserSupported,
    speech: speechStatus(state, mode === "browser" ? "ready" : engine),
    toggle, cancel, probe, clearError, reject: setError,
  };
}
