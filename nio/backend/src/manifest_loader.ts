import { readFileSync } from "fs";
import { resolve } from "path";
import { modelManifestSchema, type ModelManifest } from "../../shared/manifest-schema";

let cached: ModelManifest | null = null;

export function getManifestPath(): string {
  const envPath = process.env.MODEL_MANIFEST_PATH;
  if (envPath) {
    return resolve(envPath);
  }
  return resolve(process.cwd(), "..", "twin", "model-manifest.json");
}

export function loadManifest(force = false): ModelManifest {
  if (cached && !force) {
    return cached;
  }
  const raw = readFileSync(getManifestPath(), "utf-8");
  cached = modelManifestSchema.parse(JSON.parse(raw));
  return cached;
}
