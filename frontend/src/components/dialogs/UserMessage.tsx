export function UserMessage({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-3xl bg-orange-500 px-6 py-4 font-bold text-white sm:max-w-[70%] lg:max-w-[50%]">
        {text}
      </div>
    </div>
  );
}
