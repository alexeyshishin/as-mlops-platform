type DialogHeaderProps = {
  dialogId: number;
  intentsRecognized: number;
  started: boolean;
};

export function DialogHeader({
  dialogId,
  intentsRecognized,
  started,
}: DialogHeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-slate-100 px-4 py-4 sm:px-8 sm:py-6">
      <div>
        <h1 className="font-sans text-xl font-extrabold text-slate-900">
          {started ? `Диалог #${dialogId}` : "Начните новый диалог"}
        </h1>
        <div className="mt-1.5 flex items-center gap-2 text-sm text-slate-500">
          <span>
            Распознано типов намерений: {intentsRecognized}
          </span>
        </div>
      </div>
    </header>
  );
}
