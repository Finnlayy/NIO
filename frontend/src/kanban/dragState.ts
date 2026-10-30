import { TaskStatus } from "./types";

export interface KanbanDragState {
  taskId: string | null;
  fromStatus: TaskStatus | null;
  overStatus: TaskStatus | null;
  overIndex: number | null;
}

export function createDragState() {
  let state: KanbanDragState = {
    taskId: null,
    fromStatus: null,
    overStatus: null,
    overIndex: null,
  };

  return {
    begin(taskId: string, fromStatus: TaskStatus): void {
      state = {
        taskId,
        fromStatus,
        overStatus: null,
        overIndex: null,
      };
    },

    over(status: TaskStatus, index: number): KanbanDragState | null {
      if (!state.taskId) return null;
      state = {
        ...state,
        overStatus: status,
        overIndex: index,
      };
      return state;
    },

    drop(): { taskId: string; toStatus: TaskStatus; toIndex: number } | null {
      if (!state.taskId || !state.overStatus || state.overIndex === null) {
        this.cancel();
        return null;
      }
      const move = {
        taskId: state.taskId,
        toStatus: state.overStatus,
        toIndex: state.overIndex,
      };
      this.cancel();
      return move;
    },

    cancel(): void {
      state = {
        taskId: null,
        fromStatus: null,
        overStatus: null,
        overIndex: null,
      };
    },

    get active(): boolean {
      return state.taskId !== null;
    },

    get current(): KanbanDragState {
      return { ...state };
    }
  };
}

/**
 * Convert a drop position counted over the rendered cards (the dragged card
 * included) into the `moveTask` slot, which counts the other cards only.
 */
export function dropSlot(visibleIds: string[], taskId: string, domIndex: number): number {
  const from = visibleIds.indexOf(taskId);
  return from !== -1 && from < domIndex ? domIndex - 1 : domIndex;
}
