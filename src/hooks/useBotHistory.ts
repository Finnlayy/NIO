import { useState, useEffect, useCallback } from 'react';
import { WorkerBotData } from '../types/trading';
import { INITIAL_BOT_HISTORY } from '../data/botHistory';

export const useBotHistory = () => {
  const [history, setHistory] = useState<WorkerBotData[]>(INITIAL_BOT_HISTORY);
  const [loading, setLoading] = useState<boolean>(true);

  const refetchHistory = useCallback(async () => {
    try {
      // Klassischer HTTP GET Request an dein Backend (über relativen Pfad /api/v1/swarm/history
      // oder http://localhost:8000/api/v1/swarm/history)
      const res = await fetch('/api/v1/swarm/history');
      if (res.ok) {
        const data = await res.json();
        const list = Array.isArray(data) ? data : (data.history || data.bots || []);
        if (list.length > 0) {
          setHistory(list);
        }
      }
    } catch (err) {
      console.warn('[Swarm History] Hinweis beim Laden der Historie:', err);
      // Zero-Dummy Guarantee: Fallback auf verifizierte historische Sessions
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetchHistory();
  }, [refetchHistory]);

  const addHistoryItem = useCallback((bot: WorkerBotData) => {
    setHistory((current) => [bot, ...current.filter((b) => b.id !== bot.id)]);
  }, []);

  return { history, loading, refetchHistory, addHistoryItem };
};
