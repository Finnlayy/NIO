/** Minimal Web Speech API contract; not all browsers implement it. */
export interface BrowserRecognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: { resultIndex: number; results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

export type RecognitionConstructor = new () => BrowserRecognition;

export function browserRecognition(): RecognitionConstructor | undefined {
  if (typeof window === "undefined") return undefined;
  const browser = window as Window & {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return browser.SpeechRecognition ?? browser.webkitSpeechRecognition;
}

export function recognitionError(error: string): string {
  switch (error) {
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone blocked. Open the preview in a new tab and allow microphone access in site settings.";
    case "audio-capture":
      return "No microphone available. Check your device and browser permissions.";
    case "network":
      return "Browser speech service could not connect. Try again or use the local speech engine.";
    case "no-speech":
      return "No speech recognized. Try again and speak after the microphone starts.";
    default:
      return "Browser speech is unavailable. Try the local speech engine or type your command.";
  }
}

/** One explicit, bounded session. Delivers final text only, never executes it. */
export function startBrowserDictation(
  Recognition: RecognitionConstructor,
  language: string,
  callbacks: { onText(text: string): void; onError(message: string): void; onEnd(): void },
  maxMs = 60_000,
): { stop(): void; cancel(): void } {
  const recognition = new Recognition();
  recognition.lang = language;
  recognition.continuous = false;
  recognition.interimResults = false;
  let cancelled = false;
  let failed = false;
  let ended = false;
  const transcripts = new Map<number, string>();
  const timer = setTimeout(() => recognition.stop(), maxMs);
  recognition.onresult = (event) => {
    if (cancelled || ended) return;
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) transcripts.set(i, event.results[i][0].transcript.trim());
    }
  };
  recognition.onerror = (event) => {
    if (cancelled || ended) return;
    failed = true;
    callbacks.onError(recognitionError(event.error));
  };
  recognition.onend = () => {
    clearTimeout(timer);
    if (cancelled || ended) return;
    ended = true;
    const text = [...transcripts.entries()].sort(([a], [b]) => a - b).map(([, value]) => value).join(" ").trim();
    if (!failed) {
      if (text) callbacks.onText(text);
      else callbacks.onError(recognitionError("no-speech"));
    }
    callbacks.onEnd();
  };
  try {
    recognition.start();
  } catch (error) {
    clearTimeout(timer);
    cancelled = true;
    throw error;
  }
  return {
    stop() { if (!cancelled && !ended) recognition.stop(); },
    cancel() {
      cancelled = true;
      clearTimeout(timer);
      recognition.abort();
    },
  };
}
