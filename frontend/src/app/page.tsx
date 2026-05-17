"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AIChatSidebar } from "@/components/AIChatSidebar";
import { KanbanBoard } from "@/components/KanbanBoard";
import { getMe, logout } from "@/lib/api";

type AuthStatus = "loading" | "authenticated";

export default function Home() {
  const router = useRouter();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [chatOpen, setChatOpen] = useState(false);
  const [boardReloadSignal, setBoardReloadSignal] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((me) => {
        if (cancelled) return;
        if (!me) {
          router.replace("/login");
          return;
        }
        setStatus("authenticated");
      })
      .catch(() => {
        if (!cancelled) router.replace("/login");
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      router.replace("/login");
    }
  };

  if (status === "loading") {
    return (
      <main className="grid min-h-screen place-items-center">
        <p className="text-sm font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
          Loading...
        </p>
      </main>
    );
  }

  return (
    <>
      <KanbanBoard
        onLogout={handleLogout}
        onOpenChat={() => setChatOpen(true)}
        reloadSignal={boardReloadSignal}
      />
      <AIChatSidebar
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        onBoardUpdated={() => setBoardReloadSignal((n) => n + 1)}
      />
    </>
  );
}
