import { NODE_CATEGORY_STYLE } from "./catalog";
import type { ApolloConfiguration, NioNode } from "./types";

/* ==================================================================== */
/* Deck settings and spawned nodes across reloads                        */
/*                                                                       */
/* Quota and the failover state stay out on purpose: they are runtime    */
/* state, and a reload starts a new session on the primary.              */
/* ==================================================================== */

export const APOLLO_STORAGE_KEY = "nio.apollo.state.v1";

type SavedNode = Pick<NioNode, "id" | "label" | "category" | "position" | "metrics">;

export interface SavedApollo {
  config: ApolloConfiguration;
  nodes: NioNode[];
}

export function serializeApollo(config: ApolloConfiguration, nodes: readonly NioNode[], seedIds: ReadonlySet<string>): string {
  const { fallbackChain: _rankedOnLoad, ...routing } = config.freeLLMRouting;
  const spawned: SavedNode[] = nodes
    .filter((node) => !seedIds.has(node.id))
    .map(({ id, label, category, position, metrics }) => ({ id, label, category, position, metrics }));
  return JSON.stringify({ config: { ...config, freeLLMRouting: routing }, nodes: spawned });
}

/** Keep a saved value only when it still has the shape of the default. */
function pickSameType<T extends object>(defaults: T, saved: unknown): T {
  const merged = { ...defaults };
  if (!saved || typeof saved !== "object") return merged;
  for (const key of Object.keys(defaults) as Array<keyof T>) {
    const value = (saved as T)[key];
    if (typeof value === typeof defaults[key] && Array.isArray(value) === Array.isArray(defaults[key])) {
      merged[key] = value;
    }
  }
  return merged;
}

/** Null means nothing usable is saved. Providers keep the catalog's labels, only their status is restored. */
export function parseApollo(raw: string | null, defaults: ApolloConfiguration): SavedApollo | null {
  if (!raw) return null;
  try {
    const saved = JSON.parse(raw) as { config?: ApolloConfiguration; nodes?: unknown };
    if (!saved?.config) return null;
    const routing = defaults.freeLLMRouting;
    const savedRouting = pickSameType(routing, saved.config.freeLLMRouting);
    const config: ApolloConfiguration = {
      ...pickSameType(defaults, saved.config),
      freeLLMRouting: {
        ...savedRouting,
        weights: pickSameType(routing.weights, savedRouting.weights),
        fallbackChain: routing.fallbackChain,
        providers: routing.providers.map((provider) => {
          const match = savedRouting.providers.find((p) => p?.providerId === provider.providerId);
          return { ...provider, status: match?.status ?? provider.status };
        }),
      },
    };
    const nodes = (Array.isArray(saved.nodes) ? (saved.nodes as SavedNode[]) : [])
      .filter((node) => typeof node?.id === "string" && node.category in NODE_CATEGORY_STYLE)
      .map((node): NioNode => ({ ...node, state: "IDLE" }));
    return { config, nodes };
  } catch {
    return null;
  }
}
