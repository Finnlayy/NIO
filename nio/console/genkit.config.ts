/**
 * Config consumed by the GenKit CLI (`npx genkit start`, `npx genkit eval:run`).
 *
 * The Next.js runtime does NOT load this file; it imports the flow modules
 * directly through `src/app/api/genkit/*`.
 *
 * Importing `./genkit-flows/index` registers the plugins; importing the flow,
 * retriever, and evaluator modules causes `ai.defineFlow` / `defineRetriever`
 * / `defineEvaluator` to fire and register against the shared `ai` instance.
 */
import "./genkit-flows/index";
import "./genkit-flows/flows/echo-post-mortem.flow";
import "./genkit-flows/retrievers/ledger-retriever";
import "./genkit-flows/evaluators/post-mortem-quality";

export default {
  // Plugin list is intentionally empty: plugins are registered in
  // `genkit-flows/index.ts` so the same instance works for both the CLI and
  // the Next.js server.
};
