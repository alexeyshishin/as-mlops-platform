"use client";

import Image from "next/image";
import { Menu } from "lucide-react";
import { useMobileSidebar } from "@/components/MobileSidebarProvider";

export function MobileTopBar() {
  const { toggle } = useMobileSidebar();

  return (
    <div className="flex items-center gap-3 border-b border-slate-100 bg-white px-4 py-3 lg:hidden">
      <button
        type="button"
        onClick={toggle}
        aria-label="Открыть меню"
        className="flex size-10 shrink-0 items-center justify-center rounded-xl text-slate-500 transition-colors hover:bg-slate-100"
      >
        <Menu className="size-5" strokeWidth={2} />
      </button>
      <Image src="/logo-icon-bg.svg" alt="" width={32} height={32} className="shrink-0" />
      <span className="font-heading text-lg font-bold lowercase text-slate-900">глэк.ai</span>
    </div>
  );
}
