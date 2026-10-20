"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { useDialogsRefresh } from "@/components/DialogsRefreshProvider";
import { DialogHeader } from "@/components/dialogs/DialogHeader";
import { DialogView } from "@/components/dialogs/DialogView";
import { PastDialogView } from "@/components/dialogs/PastDialogView";
import { ApiError, getDialog, getDialogTurns, type DialogTurn } from "@/lib/api";
import { getUserId } from "@/lib/user";

const noopSubscribe = () => () => {};

function useDialogParam(): string | null {
  return useSyncExternalStore(
    noopSubscribe,
    () => new URLSearchParams(window.location.search).get("dialog"),
    () => null,
  );
}

function useUserId(): string | null {
  return useSyncExternalStore(noopSubscribe, getUserId, () => null);
}

export default function Home() {
  const dialogParam = useDialogParam();
  const userId = useUserId();
  const [sessionId] = useState(() => crypto.randomUUID());
  const [dialogId, setDialogId] = useState(1);
  const [intentsRecognized, setIntentsRecognized] = useState(0);
  const [started, setStarted] = useState(false);
  const [turns, setTurns] = useState<DialogTurn[] | null>(null);
  const { refresh: refreshDialogsList, setActiveSessionId } = useDialogsRefresh();

  const metaId = dialogParam ?? sessionId;

  useEffect(() => {
    setActiveSessionId(metaId);
    return () => setActiveSessionId(null);
  }, [metaId, setActiveSessionId]);

  const refreshMeta = useCallback(() => {
    getDialog(metaId)
      .then((meta) => {
        setDialogId(meta.seq);
        setIntentsRecognized(meta.intents_recognized);
        setStarted(true);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 404) {
          setStarted(false);
          return;
        }
        console.error(error);
      });
  }, [metaId]);

  useEffect(() => {
    refreshMeta();
  }, [refreshMeta]);

  useEffect(() => {
    if (!dialogParam) return;
    let cancelled = false;

    getDialogTurns(dialogParam)
      .then((data) => {
        if (cancelled) return;
        setTurns(data.turns);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 404) {
          setTurns([]);
          return;
        }
        console.error(error);
      });

    return () => {
      cancelled = true;
    };
  }, [dialogParam]);

  function handleClassified() {
    refreshMeta();
    refreshDialogsList();
  }

  return (
    <div className="flex h-full flex-col">
      <DialogHeader
        dialogId={dialogId}
        intentsRecognized={intentsRecognized}
        started={started}
      />
      {dialogParam
        ? turns !== null && <PastDialogView turns={turns} />
        : userId && (
            <DialogView
              sessionId={sessionId}
              userId={userId}
              onClassified={handleClassified}
            />
          )}
    </div>
  );
}
