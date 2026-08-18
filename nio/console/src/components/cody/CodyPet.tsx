"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import CodyAvatar from "./CodyAvatar";
import CodyChatPanel from "./CodyChatPanel";
import { CODY_OPEN_EVENT, useCodyPet } from "@/hooks/useCodyPet";
import { useCodyChat } from "@/hooks/useCodyChat";

const DRAG_THRESHOLD_PX = 6;
const AVATAR_SIZE = 64;

export default function CodyPet() {
  const [open, setOpen] = useState(false);
  const movedRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0, right: 24, bottom: 24 });

  const chat = useCodyChat();

  const { supervisor, commsLines, apiLive, stats, mood, anchor, anchorReady, saveAnchor } = useCodyPet({
    listening: open,
    thinking: chat.sending,
  });

  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener(CODY_OPEN_EVENT, onOpen);
    return () => window.removeEventListener(CODY_OPEN_EVENT, onOpen);
  }, []);

  const onAvatarPointerDown = useCallback(
    (e: React.PointerEvent<HTMLButtonElement>) => {
      movedRef.current = false;
      dragStartRef.current = { x: e.clientX, y: e.clientY, right: anchor.right, bottom: anchor.bottom };
      e.currentTarget.setPointerCapture(e.pointerId);
    },
    [anchor.bottom, anchor.right],
  );

  const onAvatarPointerMove = useCallback(
    (e: React.PointerEvent<HTMLButtonElement>) => {
      if (!e.currentTarget.hasPointerCapture(e.pointerId)) return;
      const dx = e.clientX - dragStartRef.current.x;
      const dy = e.clientY - dragStartRef.current.y;
      if (Math.abs(dx) > DRAG_THRESHOLD_PX || Math.abs(dy) > DRAG_THRESHOLD_PX) {
        movedRef.current = true;
      }
      if (!movedRef.current) return;
      const maxRight = Math.max(8, window.innerWidth - AVATAR_SIZE - 8);
      const maxBottom = Math.max(8, window.innerHeight - AVATAR_SIZE - 8);
      saveAnchor({
        right: Math.min(maxRight, Math.max(8, dragStartRef.current.right - dx)),
        bottom: Math.min(maxBottom, Math.max(8, dragStartRef.current.bottom - dy)),
      });
    },
    [saveAnchor],
  );

  const onAvatarPointerUp = useCallback((e: React.PointerEvent<HTMLButtonElement>) => {
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
    if (!movedRef.current) {
      setOpen((v) => !v);
    }
  }, []);

  if (!anchorReady) {
    return (
      <div className="fixed z-50 bottom-6 right-6">
        <CodyAvatar mood={mood} open={open} />
      </div>
    );
  }

  return (
    <div
      className="fixed z-50 flex flex-col-reverse items-end gap-3"
      style={{ right: anchor.right, bottom: anchor.bottom }}
    >
      <div className="relative">
        {!apiLive && !stats?.online ? (
          <span
            className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-slate-600 border border-slate-500"
            title="Backend offline"
          />
        ) : null}
        <CodyAvatar
          mood={mood}
          open={open}
          onPointerDown={onAvatarPointerDown}
          onPointerMove={onAvatarPointerMove}
          onPointerUp={onAvatarPointerUp}
        />
      </div>

      {open ? (
        <CodyChatPanel
          mood={mood}
          supervisor={supervisor}
          commsLines={commsLines}
          messages={chat.messages}
          input={chat.input}
          sending={chat.sending}
          error={chat.error}
          onInputChange={chat.setInput}
          onSend={() => void chat.send()}
          onQuickChip={(text) => void chat.send(text)}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </div>
  );
}
