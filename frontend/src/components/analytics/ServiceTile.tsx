"use client";

import { ArrowUpRight, Check, Copy, Eye, EyeOff, type LucideIcon } from "lucide-react";
import { useState, type ReactNode } from "react";

export type PlatformService = {
  id: string;
  name: string;
  description: string;
  url: string;
  icon: LucideIcon;
  accent: string;
  credentials?: { login: string; password: string };
};

export function ServiceTile({ service }: { service: PlatformService }) {
  const Icon = service.icon;

  return (
    <div className="flex flex-col gap-6 rounded-3xl border border-slate-100 bg-white p-6 shadow-sm transition-shadow hover:shadow-lg sm:p-8">
      <a
        href={service.url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-4"
      >
        <span
          className={`flex size-14 shrink-0 items-center justify-center rounded-2xl ${service.accent}`}
        >
          <Icon className="size-7" strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <h2 className="text-xl font-extrabold text-slate-900">{service.name}</h2>
          <p className="text-sm text-slate-500">{service.description}</p>
        </div>
      </a>

      {service.credentials && <CredentialsPanel credentials={service.credentials} />}

      <a
        href={service.url}
        target="_blank"
        rel="noopener noreferrer"
        className="group mt-auto inline-flex items-center gap-1.5 text-sm font-bold text-orange-500 transition-colors hover:text-orange-600"
      >
        Открыть
        <ArrowUpRight
          className="size-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
          strokeWidth={2.5}
        />
      </a>
    </div>
  );
}

function CredentialsPanel({
  credentials,
}: {
  credentials: { login: string; password: string };
}) {
  const [revealed, setRevealed] = useState(false);
  const [copiedField, setCopiedField] = useState<"login" | "password" | null>(null);

  async function copy(field: "login" | "password", value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedField(field);
      setTimeout(() => setCopiedField((current) => (current === field ? null : current)), 1500);
    } catch {}
  }

  return (
    <div className="space-y-2 rounded-2xl bg-slate-50 p-4">
      <CredentialRow
        label="Логин"
        value={credentials.login}
        copied={copiedField === "login"}
        onCopy={() => copy("login", credentials.login)}
      />
      <CredentialRow
        label="Пароль"
        value={credentials.password}
        masked={!revealed}
        copied={copiedField === "password"}
        onCopy={() => copy("password", credentials.password)}
        trailing={
          <button
            type="button"
            onClick={() => setRevealed((r) => !r)}
            aria-label={revealed ? "Скрыть пароль" : "Показать пароль"}
            className="text-slate-400 transition-colors hover:text-slate-600"
          >
            {revealed ? (
              <EyeOff className="size-4" strokeWidth={2} />
            ) : (
              <Eye className="size-4" strokeWidth={2} />
            )}
          </button>
        }
      />
    </div>
  );
}

function CredentialRow({
  label,
  value,
  masked,
  copied,
  onCopy,
  trailing,
}: {
  label: string;
  value: string;
  masked?: boolean;
  copied: boolean;
  onCopy: () => void;
  trailing?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="shrink-0 text-slate-500">{label}</span>
      <div className="flex min-w-0 items-center gap-2">
        {trailing}
        <button
          type="button"
          onClick={onCopy}
          className="flex min-w-0 items-center gap-1.5 rounded-lg px-2 py-1 font-mono font-semibold text-slate-700 transition-colors hover:bg-slate-100"
        >
          <span className="truncate">{masked ? "•".repeat(value.length) : value}</span>
          {copied ? (
            <Check className="size-3.5 shrink-0 text-emerald-500" strokeWidth={2.5} />
          ) : (
            <Copy className="size-3.5 shrink-0 text-slate-400" strokeWidth={2} />
          )}
        </button>
      </div>
    </div>
  );
}
