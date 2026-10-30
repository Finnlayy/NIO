import { useStore } from "zustand";
import { createKanbanStore, KanbanStore } from "./store";
import { createLocalStorageRepository } from "./repository";

// Ensure this singleton is initialized on the client if possible
const storage = typeof window !== "undefined" ? window.localStorage : null;
const win = typeof window !== "undefined" ? window : null;

const repository = createLocalStorageRepository(storage, win);
export const kanbanStore = createKanbanStore(repository);

export function useKanbanStore<T>(selector: (state: KanbanStore) => T): T {
  return useStore(kanbanStore, selector);
}
