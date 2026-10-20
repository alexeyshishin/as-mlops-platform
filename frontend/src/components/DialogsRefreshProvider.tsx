"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type DialogsRefreshContextValue = {
  version: number;
  refresh: () => void;
  activeSessionId: string | null;
  setActiveSessionId: (id: string | null) => void;
};

const DialogsRefreshContext = createContext<DialogsRefreshContextValue | null>(null);

export function DialogsRefreshProvider({ children }: { children: ReactNode }) {
  const [version, setVersion] = useState(0);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const refresh = useCallback(() => setVersion((v) => v + 1), []);

  return (
    <DialogsRefreshContext.Provider
      value={{ version, refresh, activeSessionId, setActiveSessionId }}
    >
      {children}
    </DialogsRefreshContext.Provider>
  );
}

export function useDialogsRefresh() {
  const ctx = useContext(DialogsRefreshContext);
  if (!ctx) {
    throw new Error("useDialogsRefresh must be used within a DialogsRefreshProvider");
  }
  return ctx;
}
