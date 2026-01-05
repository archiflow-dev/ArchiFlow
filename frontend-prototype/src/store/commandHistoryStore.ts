/**
 * Command History Store for Chat Panel
 * Provides up/down arrow navigation through sent messages
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface CommandHistoryState {
  history: string[];
  currentIndex: number;
  addToHistory: (command: string) => void;
  navigateUp: () => string;
  navigateDown: () => string;
  resetIndex: () => void;
  clearHistory: () => void;
}

export const useCommandHistoryStore = create<CommandHistoryState>()(
  persist(
    (set, get) => ({
      history: [],
      currentIndex: -1,

      addToHistory: (command: string) => {
        const trimmed = command.trim();
        if (!trimmed) return;

        set((state) => {
          // Don't add duplicate consecutive commands
          const newHistory =
            state.history[state.history.length - 1] === trimmed
              ? state.history
              : [...state.history, trimmed];

          return {
            history: newHistory,
            currentIndex: newHistory.length, // Reset to end
          };
        });
      },

      navigateUp: () => {
        const { history, currentIndex } = get();

        if (history.length === 0) return '';

        set((state) => {
          // If at end, move to last item
          if (state.currentIndex === history.length) {
            return {
              currentIndex: Math.max(0, history.length - 1),
            };
          }

          // Move up in history
          const newIndex = Math.max(0, state.currentIndex - 1);
          return {
            currentIndex: newIndex,
          };
        });

        const { currentIndex: newIndex } = get();
        return history[newIndex];
      },

      navigateDown: () => {
        const { history, currentIndex } = get();

        if (history.length === 0) return '';

        set((state) => {
          // Move down in history
          const newIndex = Math.min(history.length, state.currentIndex + 1);

          return {
            currentIndex: newIndex,
          };
        });

        const { currentIndex: newIndex } = get();

        // Return empty string if at end (user can type new command)
        if (newIndex >= history.length) {
          return '';
        }

        return history[newIndex];
      },

      resetIndex: () => {
        set({ currentIndex: -1 });
      },

      clearHistory: () => {
        set({ history: [], currentIndex: -1 });
      },
    }),
    {
      name: 'archiflow-command-history',
      partialize: (state) => ({
        history: state.history,
      }),
    }
  )
);
