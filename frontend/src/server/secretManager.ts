import { constants } from "node:fs";
import { open } from "node:fs/promises";

/** Server-only adapter for environment / an owner-only mounted JSON secret store.
 * Not an encrypted vault. Never import this module into client components.
 * Environment wins; file errors fail closed (including JSON parser messages).
 */
export async function secretEnvironment(): Promise<Record<string, string | undefined>> {
  let mounted: Record<string, string> = {};
  const path = process.env.NIO_SECRET_FILE;
  if (path) {
    try {
      const file = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
      try {
        const stat = await file.stat();
        if (!stat.isFile() || stat.size > 65_536 || (stat.mode & 0o077) !== 0 || stat.uid !== process.getuid?.()) {
          throw new Error();
        }
        const data: unknown = JSON.parse(await file.readFile("utf8"));
        if (!data || typeof data !== "object" || Array.isArray(data) ||
            Object.entries(data).some(([key, value]) => !/^[A-Z][A-Z0-9_]*$/.test(key) || typeof value !== "string")) {
          throw new Error();
        }
        mounted = data as Record<string, string>;
      } finally { await file.close(); }
    } catch { throw new Error("secret_store_unavailable_or_invalid"); }
  }
  return { ...mounted, ...process.env };
}
