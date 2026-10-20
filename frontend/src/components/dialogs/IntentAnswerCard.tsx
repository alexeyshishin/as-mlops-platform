"use client";

import {
  Children,
  cloneElement,
  isValidElement,
  useEffect,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import type { LucideIcon } from "lucide-react";
import { randomScramblePair } from "@/lib/scramble";
import { FadeIn } from "./FadeIn";

export type ConfidenceTier = "high" | "medium" | "low";

export function getConfidenceTier(confidence: number): ConfidenceTier {
  if (confidence >= 80) return "high";
  if (confidence >= 40) return "medium";
  return "low";
}

const CARD_TONE = {
  high: "border-emerald-200 bg-emerald-50/60",
  medium: "border-amber-200 bg-amber-50/60",
  low: "border-dashed border-slate-300 bg-slate-50/70",
} satisfies Record<ConfidenceTier, string>;

const BADGE_TONE = {
  high: "bg-emerald-100 text-emerald-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-slate-100 text-slate-600",
} satisfies Record<ConfidenceTier, string>;

const DOT_TONE = {
  high: "bg-emerald-500",
  medium: "bg-amber-600",
  low: "bg-slate-600",
} satisfies Record<ConfidenceTier, string>;

const LABEL_TONE = {
  high: "text-emerald-600",
  medium: "text-amber-600",
  low: "text-slate-500",
} satisfies Record<ConfidenceTier, string>;

const ATTACHMENT_ICON_TONE = {
  high: "bg-emerald-100 text-emerald-600",
  medium: "bg-amber-100 text-amber-600",
  low: "bg-slate-100 text-slate-600",
} satisfies Record<ConfidenceTier, string>;

const SCRAMBLE_INTERVAL_MS = 80;

type IntentAnswerCardProps = {
  confidence?: number;
  note?: string;
  badgeLabel?: string;
  children?: ReactNode;
  pending?: boolean;
};

export function IntentAnswerCard({
  confidence,
  note,
  badgeLabel,
  children,
  pending = false,
}: IntentAnswerCardProps) {
  const [scramble, setScramble] = useState(randomScramblePair);

  useEffect(() => {
    if (!pending) return;
    const id = setInterval(() => setScramble(randomScramblePair()), SCRAMBLE_INTERVAL_MS);
    return () => clearInterval(id);
  }, [pending]);

  const resolved = !pending;
  const finalTier = getConfidenceTier(confidence ?? 0);
  const tier = resolved ? finalTier : "low";

  const content = Children.map(children, (child) => {
    if (isValidElement(child) && child.type === Attachment) {
      return cloneElement(child as ReactElement<AttachmentProps>, { tone: finalTier });
    }
    return child;
  });

  return (
    <div
      className={`w-fit max-w-[85%] self-start rounded-2xl border p-6 transition-colors duration-700 ease-out sm:max-w-[70%] lg:max-w-[50%] ${CARD_TONE[tier]}`}
    >
      <div className="mb-4 flex items-center justify-between gap-4">
        <div
          className={`inline-flex items-center gap-2 whitespace-nowrap rounded-full px-4 py-2 transition-colors duration-700 ease-out ${BADGE_TONE[tier]}`}
        >
          <span
            className={`size-2.5 shrink-0 rounded-full transition-colors duration-700 ease-out ${DOT_TONE[tier]}`}
          />
          {resolved ? (
            <span className="text-sm font-bold">
              {confidence ?? 0}% уверенности ответа
              {note ? ` - ${note}` : ""}
            </span>
          ) : (
            <span className="font-mono text-sm font-bold tabular-nums">
              {scramble}% уверенности ответа
            </span>
          )}
        </div>

        {resolved && badgeLabel && (
          <FadeIn className="shrink-0">
            <span className={`font-semibold ${LABEL_TONE[tier]}`}>{badgeLabel}</span>
          </FadeIn>
        )}
      </div>

      {resolved ? (
        <FadeIn className="space-y-4 text-base leading-relaxed text-slate-900">
          {content}
        </FadeIn>
      ) : (
        <div className="skeleton-shimmer h-6 w-56 max-w-full rounded-full" />
      )}
    </div>
  );
}

type AttachmentProps = {
  icon: LucideIcon;
  title: string;
  subtitle: string;
  tone?: ConfidenceTier;
};

function Attachment({ icon: Icon, title, subtitle, tone = "high" }: AttachmentProps) {
  return (
    <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4">
      <span
        className={`flex size-12 shrink-0 items-center justify-center rounded-full ${ATTACHMENT_ICON_TONE[tone]}`}
      >
        <Icon className="size-6" strokeWidth={2} />
      </span>
      <div className="min-w-0">
        <p className="font-bold text-slate-900">{title}</p>
        <p className="text-sm text-slate-400">{subtitle}</p>
      </div>
    </div>
  );
}

IntentAnswerCard.Attachment = Attachment;

type QuickRepliesProps = {
  options: string[];
};

function QuickReplies({ options }: QuickRepliesProps) {
  return (
    <div className="flex flex-col gap-3">
      {options.map((option) => (
        <button
          key={option}
          type="button"
          className="rounded-full bg-slate-100 px-6 py-4 text-center font-bold text-slate-900 transition-colors hover:bg-slate-200"
        >
          {option}
        </button>
      ))}
    </div>
  );
}

IntentAnswerCard.QuickReplies = QuickReplies;
