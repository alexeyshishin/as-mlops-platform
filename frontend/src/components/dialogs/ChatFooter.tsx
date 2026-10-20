"use client";

import { ArrowUpRight } from "lucide-react";
import { useState, type FormEvent } from "react";

type ChatFooterProps = {
  onSubmit: (value: string) => void;
};

export function ChatFooter({ onSubmit }: ChatFooterProps) {
  const [value, setValue] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    setValue("");
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-center gap-3 rounded-2xl border border-slate-100 bg-slate-50 p-2 pl-4"
    >
      <input
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Введите ваш запрос для AI Ассистента..."
        className="min-w-0 flex-1 bg-transparent text-slate-600 outline-none placeholder:text-slate-400"
      />
      <button
        type="submit"
        aria-label="Отправить"
        className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-orange-500 text-white transition-colors hover:bg-orange-600"
      >
        <ArrowUpRight className="size-5" strokeWidth={2.5} />
      </button>
    </form>
  );
}
