/* ==================================================================== */
/* Optional live bridge                                                  */
/*                                                                       */
/* The UI is fully functional without a backend: synthesis is simulated  */
/* and every simulated line is labelled SIM. When an operator configures  */
/* a FreeLLMAPI endpoint, prompts go through `/api/apollo`, which proxies */
/* to that OpenAI-compatible endpoint. Failures degrade to simulation     */
/* with a visible warning — never to a silent fake answer.               */
/* ==================================================================== */

export interface SynthesisRequest {
  endpointUrl: string;
  model: string;
  messages: Array<{ role: "system" | "user" | "assistant"; content: string }>;
  temperature: number;
  maxTokens: number;
}

export interface SynthesisResult {
  ok: boolean;
  text: string;
  provider?: string;
  model?: string;
  latencyMs?: number;
  error?: string;
}

/** Ask the server-side proxy; never call a third-party origin from the tab. */
export async function requestSynthesis(payload: SynthesisRequest): Promise<SynthesisResult> {
  const started = Date.now();
  try {
    const response = await fetch("/api/apollo", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(25_000),
    });
    const data = (await response.json()) as {
      ok?: boolean;
      text?: string;
      provider?: string;
      model?: string;
      error?: string;
    };
    return {
      ok: Boolean(response.ok && data.ok),
      text: data.text ?? "",
      provider: data.provider,
      model: data.model,
      latencyMs: Date.now() - started,
      error: data.error ?? (response.ok ? undefined : `HTTP ${response.status}`),
    };
  } catch (error) {
    return {
      ok: false,
      text: "",
      latencyMs: Date.now() - started,
      error: error instanceof Error ? error.message : "network error",
    };
  }
}

export interface SandboxResult {
  ok: boolean;
  command: string;
  stdout: string;
  code: number;
  error?: string;
  mode?: string;
}

/** Read-only command jail; the route enforces the allowlist, not the client. */
export async function runSandboxCommand(command: string): Promise<SandboxResult> {
  try {
    const response = await fetch("/api/sandbox", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ command }),
      signal: AbortSignal.timeout(8_000),
    });
    const data = (await response.json()) as Partial<SandboxResult> & { error?: string };
    return {
      ok: Boolean(response.ok && data.ok),
      command,
      stdout: data.stdout ?? "",
      code: data.code ?? (response.ok ? 0 : 1),
      error: data.error,
      mode: data.mode,
    };
  } catch (error) {
    return {
      ok: false,
      command,
      stdout: "",
      code: 1,
      error: error instanceof Error ? error.message : "network error",
    };
  }
}

export interface VaultNote {
  path: string;
  title: string;
  snippet: string;
}

export interface VaultResult {
  ok: boolean;
  path?: string;
  committed?: boolean;
  notes?: VaultNote[];
  error?: string;
}

/** Notes stay on this machine; the route runs them through the orchestrator. */
export async function callVault(request: { action: "search"; query: string } | { action: "capture"; text: string }): Promise<VaultResult> {
  try {
    const response = await fetch("/api/apollo/vault", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
      signal: AbortSignal.timeout(16_000),
    });
    const data = (await response.json()) as Partial<VaultResult>;
    return { ...data, ok: Boolean(response.ok && data.ok) };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "network error" };
  }
}
