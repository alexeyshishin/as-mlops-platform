import { Fragment } from "react";
import type { DialogTurn } from "@/lib/api";
import { UserMessage } from "./UserMessage";

export function PastDialogView({ turns }: { turns: DialogTurn[] }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="flex w-full flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8">
          {turns.length === 0 && (
            <p className="pt-8 text-center text-slate-400">
              В этом диалоге пока нет сообщений.
            </p>
          )}

          {turns.map((turn, index) => (
            <Fragment key={index}>
              <UserMessage text={turn.text} />
              <div className="w-fit max-w-[85%] self-start rounded-2xl border border-slate-200 bg-slate-50/70 p-6 text-base leading-relaxed text-slate-900 sm:max-w-[70%] lg:max-w-[50%]">
                {turn.intent ? (
                  <p>
                    Интент: <strong>{turn.intent}</strong>
                  </p>
                ) : (
                  <p className="text-slate-500">интент не распознан</p>
                )}
              </div>
            </Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}
