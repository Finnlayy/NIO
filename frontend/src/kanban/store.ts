import { createStore } from "zustand/vanilla";
import { BoardState, KanbanTask, BoardFilter, TaskStatus } from "./types";
import { BoardRepository } from "./repository";
import { createSeedBoard } from "./seed";
import {
  localToday,
  addTask,
  updateTask,
  moveTask,
  removeTask,
  restoreTask,
  addChecklistItem,
  toggleChecklistItem,
  renameChecklistItem,
  removeChecklistItem,
  type RemovedTask,
} from "./board-logic";

export interface KanbanStoreState {
  board: BoardState;
  hydrated: boolean;
  filter: BoardFilter;
  saveFailed: boolean;
  lastRemoved: RemovedTask | null;
}

export interface KanbanStoreActions {
  hydrate: () => void;
  addTask: (draft: Omit<KanbanTask, "id" | "order" | "createdAt" | "updatedAt">) => void;
  updateTask: (id: string, patch: Partial<Omit<KanbanTask, "id" | "createdAt" | "updatedAt">>) => void;
  moveTask: (taskId: string, toStatus: TaskStatus, toVisibleIndex: number, visibleIds: string[]) => void;
  removeTask: (id: string) => void;
  undoRemove: () => void;
  addChecklistItem: (taskId: string, title: string) => void;
  toggleChecklistItem: (taskId: string, itemId: string) => void;
  renameChecklistItem: (taskId: string, itemId: string, title: string) => void;
  removeChecklistItem: (taskId: string, itemId: string) => void;
  setLabelFilter: (labelIds: string[]) => void;
  setAssigneeFilter: (assigneeIds: string[]) => void;
  resetFilters: () => void;
  /** Stop listening for changes from other tabs. */
  dispose: () => void;
}

export type KanbanStore = KanbanStoreState & KanbanStoreActions;

export function createKanbanStore(
  repo: BoardRepository,
  opts?: { now?: () => string; today?: () => string }
) {
  const getNow = opts?.now || (() => new Date().toISOString());
  const getToday = opts?.today || (() => localToday());

  return createStore<KanbanStore>((set, get) => {
    let unsubscribe: (() => void) | null = null;

    /* Every board change goes through here; it persists only once hydrated,
       so the seed board can never overwrite stored data. */
    function updateBoard(newBoard: BoardState) {
      const state = get();
      if (newBoard === state.board) return;

      let saveFailed = state.saveFailed;
      if (state.hydrated) {
        const success = repo.save(newBoard);
        saveFailed = !success;
      }

      set({ board: newBoard, saveFailed });
    }

    function patchChecklist(taskId: string, change: (task: KanbanTask) => KanbanTask) {
      const board = get().board;
      const task = board.tasks.find((t) => t.id === taskId);
      if (!task) return;
      const patched = change(task);
      if (JSON.stringify(patched.checklist) === JSON.stringify(task.checklist)) return;
      updateBoard(updateTask(board, taskId, { checklist: patched.checklist }, getNow()));
    }

    return {
      board: createSeedBoard(getToday()),
      hydrated: false,
      filter: { labelIds: [], assigneeIds: [] },
      saveFailed: false,
      lastRemoved: null,

      hydrate: () => {
        const state = get();
        if (state.hydrated) return;

        const { board: loadedBoard, recovered } = repo.load();
        const nextBoard = loadedBoard || state.board;

        let saveFailed = state.saveFailed;

        // Another tab saved: take its board as-is (no save back, that would echo).
        unsubscribe = repo.subscribe((externalBoard) => {
          if (externalBoard) set({ board: externalBoard });
        });

        // Persist field-level repairs right away.
        if (recovered && loadedBoard) saveFailed = !repo.save(loadedBoard);

        set({ board: nextBoard, hydrated: true, saveFailed });
      },

      addTask: (draft) => {
        updateBoard(addTask(get().board, draft, getNow()));
      },

      updateTask: (id, patch) => {
        updateBoard(updateTask(get().board, id, patch, getNow()));
      },

      moveTask: (taskId, toStatus, toVisibleIndex, visibleIds) => {
        updateBoard(moveTask(get().board, taskId, toStatus, toVisibleIndex, visibleIds, getNow()));
      },

      removeTask: (id) => {
        const { board, removed } = removeTask(get().board, id);
        if (removed) {
          set({ lastRemoved: removed });
          updateBoard(board);
        }
      },

      undoRemove: () => {
        const { board, lastRemoved } = get();
        if (!lastRemoved) return;
        updateBoard(restoreTask(board, lastRemoved));
        set({ lastRemoved: null });
      },

      addChecklistItem: (taskId, title) => patchChecklist(taskId, (t) => addChecklistItem(t, title)),
      toggleChecklistItem: (taskId, itemId) => patchChecklist(taskId, (t) => toggleChecklistItem(t, itemId)),
      renameChecklistItem: (taskId, itemId, title) => patchChecklist(taskId, (t) => renameChecklistItem(t, itemId, title)),
      removeChecklistItem: (taskId, itemId) => patchChecklist(taskId, (t) => removeChecklistItem(t, itemId)),

      setLabelFilter: (labelIds) => {
        set((state) => ({ filter: { ...state.filter, labelIds } }));
      },

      setAssigneeFilter: (assigneeIds) => {
        set((state) => ({ filter: { ...state.filter, assigneeIds } }));
      },

      resetFilters: () => {
        set({ filter: { labelIds: [], assigneeIds: [] } });
      },

      dispose: () => {
        unsubscribe?.();
        unsubscribe = null;
      },
    };
  });
}
