import React, { useState, KeyboardEvent } from "react";
import { ChecklistItem } from "./types";
import { Plus, X } from "lucide-react";
import { newId } from "./board-logic";

interface ChecklistEditorProps {
  items: ChecklistItem[];
  onChange: (items: ChecklistItem[]) => void;
}

export const ChecklistEditor: React.FC<ChecklistEditorProps> = ({ items, onChange }) => {
  const [newItemTitle, setNewItemTitle] = useState("");

  const handleAdd = () => {
    const trimmed = newItemTitle.trim();
    if (!trimmed) return;

    onChange([...items, { id: newId("chk"), title: trimmed, completed: false }]);
    setNewItemTitle("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      handleAdd();
    }
  };

  const handleToggle = (id: string) => {
    onChange(items.map(item =>
      item.id === id ? { ...item, completed: !item.completed } : item
    ));
  };

  const handleTitleChange = (id: string, newTitle: string) => {
    onChange(items.map(item =>
      item.id === id ? { ...item, title: newTitle } : item
    ));
  };

  const handleBlur = (id: string, newTitle: string) => {
    if (newTitle.trim() === "") {
      onChange(items.filter(item => item.id !== id));
    }
  };

  const handleRemove = (id: string) => {
    onChange(items.filter(item => item.id !== id));
  };

  const completedCount = items.filter(item => item.completed).length;
  const totalCount = items.length;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between text-xs font-medium text-slate-300">
        <span>Checkliste</span>
        {totalCount > 0 && (
          <span className="text-slate-500">
            {completedCount}/{totalCount}
          </span>
        )}
      </div>

      <div className="flex flex-col gap-2">
        {items.map((item) => (
          <div key={item.id} className="flex items-center gap-2 group">
            <input
              type="checkbox"
              checked={item.completed}
              onChange={() => handleToggle(item.id)}
              className="w-4 h-4 rounded border-white/20 bg-white/5 checked:bg-cyan-500 checked:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:ring-offset-1 focus:ring-offset-[#0f111a] shrink-0"
              aria-label={item.title}
            />
            <input
              type="text"
              value={item.title}
              onChange={(e) => handleTitleChange(item.id, e.target.value)}
              onBlur={(e) => handleBlur(item.id, e.target.value)}
              className={`flex-1 bg-transparent border-none text-sm focus:outline-none focus:ring-1 focus:ring-white/20 rounded px-1 -ml-1 ${
                item.completed ? "text-slate-500 line-through" : "text-slate-200"
              }`}
            />
            <button
              onClick={() => handleRemove(item.id)}
              aria-label={`Punkt entfernen: ${item.title}`}
              className="p-1 text-slate-500 hover:text-red-400 hover:bg-white/10 rounded opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 mt-1">
        <Plus className="w-4 h-4 text-slate-500" />
        <input
          type="text"
          value={newItemTitle}
          onChange={(e) => setNewItemTitle(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleAdd}
          placeholder="Punkt hinzufügen"
          className="flex-1 bg-transparent border-none text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-white/20 rounded px-1 -ml-1"
        />
      </div>
    </div>
  );
};
