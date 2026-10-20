"use client";

import { useCallback, useEffect, useRef, useState, Fragment } from "react";
import { ApiError, classify, type ClassifyResponse } from "@/lib/api";
import { ChatFooter } from "./ChatFooter";
import { IntentAnswerCard } from "./IntentAnswerCard";
import { UserMessage } from "./UserMessage";

type Message = {
  id: string;
  userText: string;
  status: "pending" | "resolved" | "error";
  response?: ClassifyResponse;
  errorMessage?: string;
};

function RawAnswerBody({ response }: { response: ClassifyResponse }) {
  const { intent } = response;
  const rest = { ...response };
  delete rest.intent;
  delete rest.confidence;
  const hasRest = Object.keys(rest).length > 0;

  return (
    <div className="space-y-3">
      {intent && (
        <p>
          Интент: <strong>{String(intent)}</strong>
        </p>
      )}
      {hasRest && (
        <pre className="overflow-x-auto rounded-xl bg-white/70 p-3 font-mono text-xs text-slate-600">
          {JSON.stringify(rest, null, 2)}
        </pre>
      )}
    </div>
  );
}

function ErrorAnswerCard({ message }: { message: string }) {
  return (
    <div className="w-fit max-w-[85%] self-start rounded-2xl border border-rose-200 bg-rose-50/70 p-4 text-sm text-rose-700 sm:max-w-[70%] lg:max-w-[50%]">
      Не удалось получить ответ: {message}
    </div>
  );
}

function AnswerCard({ message }: { message: Message }) {
  if (message.status === "error") {
    return <ErrorAnswerCard message={message.errorMessage ?? "неизвестная ошибка"} />;
  }

  const response = message.response;
  const confidence = response?.confidence;

  return (
    <IntentAnswerCard
      pending={message.status === "pending"}
      confidence={
        typeof confidence === "number"
          ? Math.round(confidence <= 1 ? confidence * 100 : confidence)
          : undefined
      }
    >
      {response && <RawAnswerBody response={response} />}
    </IntentAnswerCard>
  );
}

export function DialogView({
  sessionId,
  userId,
  onClassified,
}: {
  sessionId: string;
  userId: string;
  onClassified?: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  async function handleSubmit(value: string) {
    const id = crypto.randomUUID();
    const history = messages.map((m) => ({ role: "user" as const, content: m.userText }));

    setMessages((prev) => [...prev, { id, userText: value, status: "pending" }]);

    try {
      const response = await classify({ sessionId, userId, history, text: value });
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, status: "resolved", response } : m)),
      );
      onClassified?.();
    } catch (error) {
      const errorMessage = error instanceof ApiError ? error.message : "неизвестная ошибка";
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, status: "error", errorMessage } : m)),
      );
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        <div className="flex w-full flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8">
          {messages.length === 0 && (
            <p className="pt-8 text-center text-slate-400">
              Напишите сообщение — ассистент ответит через /classify.
            </p>
          )}

          {messages.map((message) => (
            <Fragment key={message.id}>
              <UserMessage text={message.userText} />
              <AnswerCard message={message} />
            </Fragment>
          ))}
        </div>
      </div>

      <div className="border-t border-slate-100 px-4 py-3 sm:px-8 sm:py-4">
        <ChatFooter onSubmit={handleSubmit} />
      </div>
    </div>
  );
}
