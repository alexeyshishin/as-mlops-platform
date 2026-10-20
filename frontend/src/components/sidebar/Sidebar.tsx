"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BarChart3,
  MessageCircle,
  Plus,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { deleteDialog, listDialogs, type Dialog } from "@/lib/api";
import { getUserId } from "@/lib/user";
import { useDialogsRefresh } from "@/components/DialogsRefreshProvider";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useMobileSidebar } from "@/components/MobileSidebarProvider";

type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

const NAV_ITEMS: NavItem[] = [
  { label: "Диалоги", href: "/", icon: MessageCircle },
  { label: "Аналитика интентов", href: "/analytics", icon: BarChart3 },
];

export function Sidebar() {
  const [dialogs, setDialogs] = useState<Dialog[] | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmTarget, setConfirmTarget] = useState<Dialog | null>(null);
  const { version, activeSessionId } = useDialogsRefresh();
  const pathname = usePathname();
  const { isOpen } = useMobileSidebar();

  function requestDelete(dialog: Dialog) {
    if (deletingId) return;
    setConfirmTarget(dialog);
  }

  function cancelDelete() {
    if (deletingId) return;
    setConfirmTarget(null);
  }

  async function confirmDelete() {
    if (!confirmTarget) return;
    const sessionId = confirmTarget.session_id;
    setDeletingId(sessionId);
    try {
      await deleteDialog(sessionId, getUserId());
    } catch (error) {
      console.error(error);
      setDeletingId(null);
      setConfirmTarget(null);
      return;
    }
    setConfirmTarget(null);
    if (sessionId === activeSessionId) {
      window.location.assign("/");
      return;
    }
    setDialogs((prev) => (prev ? prev.filter((d) => d.session_id !== sessionId) : prev));
    setDeletingId(null);
  }

  useEffect(() => {
    let cancelled = false;

    listDialogs(getUserId())
      .then((data) => {
        if (cancelled) return;
        setDialogs(data);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        console.error(error);
        setDialogs([]);
      });

    return () => {
      cancelled = true;
    };
  }, [version]);

  return (
    <>
      <SidebarBackdrop />

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[280px] shrink-0 flex-col overflow-y-auto border-r border-slate-100 bg-white px-4 py-6 transition-transform duration-300 ease-in-out lg:static lg:z-auto lg:translate-x-0 lg:transition-none ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <a href={"/"} className="mb-8 flex items-center gap-3 px-2">
          <Image
            src="/logo-icon-bg.svg"
            alt=""
            width={48}
            height={48}
            className="shrink-0"
            priority
          />
          <span className="font-heading text-2xl font-bold lowercase text-slate-900">
            глэк.ai
          </span>
        </a>

        <a
          href={"/"}
          className="mb-4 flex items-center gap-3 rounded-xl bg-orange-500 px-3 py-2.5 font-semibold text-white transition-colors hover:bg-orange-600"
        >
          <Plus className="size-5 shrink-0" strokeWidth={2} />
          <span>Новый диалог</span>
        </a>

        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <SidebarLink
              key={item.href}
              item={item}
              active={pathname === item.href}
              showDot={item.href === "/"}
            />
          ))}
        </nav>

        <div className="my-4 border-t border-slate-100" />

        <nav className="flex flex-col gap-1">
          {dialogs === null && (
            <p className="px-3 py-2.5 text-sm text-slate-400">Загрузка…</p>
          )}
          {dialogs?.length === 0 && (
            <p className="px-3 py-2.5 text-sm text-slate-400">Диалогов пока нет</p>
          )}
          {dialogs?.map((dialog) => (
            <div
              key={dialog.session_id}
              className="group flex items-center rounded-xl text-slate-500 transition-colors hover:bg-slate-50"
            >
              <a
                href={`/?dialog=${dialog.session_id}`}
                className="flex min-w-0 flex-1 items-center gap-3 px-3 py-2.5"
              >
                <MessageCircle className="size-5 shrink-0" strokeWidth={2} />
                <span className="truncate text-[15px]">{dialog.label}</span>
              </a>
              <button
                type="button"
                aria-label="Удалить диалог"
                onClick={() => requestDelete(dialog)}
                disabled={deletingId === dialog.session_id}
                className="mr-2 shrink-0 rounded-lg p-1.5 text-slate-400 opacity-0 transition-colors hover:text-red-500 group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Trash2 className="size-4" strokeWidth={2} />
              </button>
            </div>
          ))}
        </nav>

        {confirmTarget && (
          <ConfirmDialog
            title="Удалить диалог?"
            message={`Диалог «${confirmTarget.label}» будет удалён без возможности восстановления.`}
            pending={deletingId === confirmTarget.session_id}
            onConfirm={confirmDelete}
            onCancel={cancelDelete}
          />
        )}

        <div className="mt-auto pt-4">
          <div className="mb-4 border-t border-slate-100" />
          <div className="px-3 text-xs leading-relaxed text-slate-400">
            <p className="mb-1 font-semibold text-slate-500">О сервисе</p>
            <p>
              Сервис разработан группой компаний{" "}
              <span className="font-medium text-slate-600">CakeDev</span> мощными и сочными
              ребятами из{" "}
              <span className="font-medium text-slate-600">MWS</span>,{" "}
              <span className="font-medium text-slate-600">Бюро 1703</span> и{" "}
              <a
                href="https://neiry.ru"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-slate-600 underline decoration-slate-300 underline-offset-2 hover:text-orange-500"
              >
                neiry.ru
              </a>
              .
            </p>
          </div>
        </div>
      </aside>
    </>
  );
}

function SidebarBackdrop() {
  const { isOpen, close } = useMobileSidebar();

  if (!isOpen) return null;

  return (
    <div
      onClick={close}
      aria-hidden="true"
      className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden"
    />
  );
}

function SidebarLink({
  item,
  active,
  showDot,
}: {
  item: NavItem;
  active: boolean;
  showDot: boolean;
}) {
  const Icon = item.icon;
  const className = active
    ? "flex items-center gap-3 rounded-xl bg-slate-100 px-3 py-2.5 font-semibold text-slate-900"
    : "flex items-center gap-3 rounded-xl px-3 py-2.5 text-slate-500 transition-colors hover:bg-slate-50";
  const children = (
    <>
      <Icon
        className={active ? "size-5 shrink-0 text-orange-500" : "size-5 shrink-0"}
        strokeWidth={2}
      />
      <span className="flex-1 truncate text-[15px]">{item.label}</span>
      {showDot && (
        <span className="size-2 shrink-0 rounded-full bg-orange-500" />
      )}
    </>
  );

  if (item.href === "/") {
    return (
      <a href={item.href} className={className}>
        {children}
      </a>
    );
  }

  return (
    <Link href={item.href} className={className}>
      {children}
    </Link>
  );
}
