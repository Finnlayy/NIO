import { Metadata } from "next";
import { KanbanBoard } from "../../kanban/KanbanBoard";

export const metadata: Metadata = {
  title: "Kanban · NIO",
};

export default function KanbanPage() {
  return <KanbanBoard />;
}
