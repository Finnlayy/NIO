import { BoardState } from "./types";
import { parseStoredBoard } from "./validate";

/**
 * Interface for board persistence.
 * A server/Hermes adapter can implement this later to sync with a backend.
 */
export interface BoardRepository {
  load(): { board: BoardState | null; recovered: boolean };
  save(board: BoardState): boolean;
  subscribe(onExternalChange: (board: BoardState | null) => void): () => void;
}

export function createLocalStorageRepository(
  storage?: Storage | null,
  win?: EventTarget | null
): BoardRepository {
  const KEY = "nio.kanban.v1";

  return {
    load(): { board: BoardState | null; recovered: boolean } {
      if (!storage) return { board: null, recovered: false };

      let raw: string | null = null;
      try {
        raw = storage.getItem(KEY);
      } catch (e) {
        // e.g. SecurityError in private mode
        return { board: null, recovered: false };
      }

      if (!raw) return { board: null, recovered: false };

      const { board, recovered, reason } = parseStoredBoard(raw);

      if (board === null && recovered) {
        // Hard failure on parsing, save the corrupt payload backup
        try {
          const backupKey = `nio.kanban.v1.corrupt-${Date.now()}`;
          storage.setItem(backupKey, raw);
        } catch (e) {
          // ignore backup errors
        }
      }

      return { board, recovered };
    },

    save(board: BoardState): boolean {
      if (!storage) return false;
      try {
        const raw = JSON.stringify(board);
        storage.setItem(KEY, raw);
        return true;
      } catch (e) {
        return false;
      }
    },

    subscribe(onExternalChange: (board: BoardState | null) => void): () => void {
      if (!win) return () => {};

      const handler = (e: Event) => {
        const ev = e as StorageEvent;
        if (ev.key === KEY) {
          if (!ev.newValue) {
            onExternalChange(null);
          } else {
            const { board } = parseStoredBoard(ev.newValue);
            onExternalChange(board);
          }
        }
      };

      win.addEventListener("storage", handler);
      return () => {
        win.removeEventListener("storage", handler);
      };
    },
  };
}
