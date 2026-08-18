/**
 * GenKit runtime singleton for Nexus.
 *
 * One `ai` instance is shared by every flow, retriever, evaluator, and the
 * Next.js API routes. Plugins are registered once; Google Cloud telemetry is
 * opt-in so local development without Application Default Credentials does not
 * crash the dev server.
 *
 * NOTE on the folder name: this directory is `genkit-flows/` (not `genkit/`)
 * on purpose. A folder called `genkit/` collides with the npm package of the
 * same name and breaks TypeScript module resolution for `import … from "genkit"`.
 */
import { genkit } from "genkit";
import { vertexAI, gemini25FlashPreview0417 } from "@genkit-ai/vertexai";

const projectId = process.env.PROJECT_ID ?? process.env.GOOGLE_CLOUD_PROJECT;
const location = process.env.VERTEX_AI_LOCATION ?? "europe-west3";

const plugins = [
  vertexAI({
    projectId: projectId ?? "local-dev",
    location,
  }),
];

// Cloud Trace + Cloud Logging telemetry. Only enable when a project id is
// present AND the operator explicitly opted in via GENKIT_TELEMETRY=1, so
// local runs without Application Default Credentials do not block on ADC
// discovery.
if (projectId && process.env.GENKIT_TELEMETRY === "1") {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const gcp = require("@genkit-ai/google-cloud") as typeof import("@genkit-ai/google-cloud");
  gcp.enableGoogleCloudTelemetry({ projectId });
}

export const ai = genkit({
  plugins,
  model: gemini25FlashPreview0417,
});

export const GENKIT_RUNTIME = {
  projectId: projectId ?? null,
  location,
  telemetry: Boolean(projectId) && process.env.GENKIT_TELEMETRY === "1",
  model: "gemini-2.5-flash-preview-04-17",
};
