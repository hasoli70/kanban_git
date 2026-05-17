"use client";

import { useEffect, useRef, useState } from "react";

import { ApiError, chatAI, type ChatMessage } from "@/lib/api";

type AIChatSidebarProps = {
  open: boolean;
  onClose: () => void;
  onBoardUpdated: () => void;
};

type DisplayMessage =
  | { role: "user" | "assistant"; content: string }
  | { role: "system"; content: string };

export const AIChatSidebar = ({
  open,
  onClose,
  onBoardUpdated,
}: AIChatSidebarProps) => {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const history: ChatMessage[] = messages
      .filter((m): m is ChatMessage => m.role === "user" || m.role === "assistant")
      .map((m) => ({ role: m.role, content: m.content }));

    const userMessage: DisplayMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setError(null);
    setLoading(true);

    try {
      const result = await chatAI(text, history);
      const reply: DisplayMessage = { role: "assistant", content: result.reply };
      setMessages((prev) => {
        const next: DisplayMessage[] = [...prev, reply];
        if (result.board_updated) {
          next.push({ role: "system", content: "Board updated." });
        } else if (result.validation_error) {
          next.push({
            role: "system",
            content: `Update rejected: ${result.validation_error}`,
          });
        }
        return next;
      });
      if (result.board_updated) {
        onBoardUpdated();
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to reach the AI service.",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void send();
  };

  if (!open) return null;

  return (
    <aside
      aria-label="AI chat"
      className="fixed right-0 top-0 z-30 flex h-screen w-full max-w-sm flex-col border-l border-[var(--stroke)] bg-white/95 shadow-[var(--shadow)] backdrop-blur"
    >
      <header className="flex items-center justify-between border-b border-[var(--stroke)] px-5 py-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--gray-text)]">
            AI Assistant
          </p>
          <h2 className="mt-1 font-display text-lg font-semibold text-[var(--navy-dark)]">
            Board chat
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close chat"
          className="rounded-full border border-[var(--stroke)] bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)] hover:bg-[var(--surface)]"
        >
          Close
        </button>
      </header>

      <div
        ref={listRef}
        className="flex-1 overflow-y-auto px-5 py-4"
        data-testid="chat-message-list"
      >
        {messages.length === 0 && !loading ? (
          <p className="text-sm leading-6 text-[var(--gray-text)]">
            Ask me to add a card, move things between columns, or summarise what
            is in progress.
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {messages.map((message, idx) => (
              <li
                key={idx}
                data-role={message.role}
                className={
                  message.role === "user"
                    ? "self-end rounded-2xl bg-[var(--primary-blue)] px-4 py-2 text-sm text-white"
                    : message.role === "assistant"
                      ? "self-start rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-2 text-sm text-[var(--navy-dark)]"
                      : "self-center rounded-full bg-[var(--surface)] px-3 py-1 text-xs uppercase tracking-[0.2em] text-[var(--gray-text)]"
                }
              >
                {message.content}
              </li>
            ))}
            {loading ? (
              <li className="self-start rounded-2xl border border-dashed border-[var(--stroke)] bg-white px-4 py-2 text-sm italic text-[var(--gray-text)]">
                Thinking...
              </li>
            ) : null}
          </ul>
        )}
      </div>

      {error ? (
        <div
          role="alert"
          className="mx-5 mb-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700"
        >
          {error}
        </div>
      ) : null}

      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 border-t border-[var(--stroke)] px-5 py-4"
      >
        <label htmlFor="ai-chat-input" className="sr-only">
          Message
        </label>
        <input
          id="ai-chat-input"
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the assistant..."
          disabled={loading}
          className="flex-1 rounded-full border border-[var(--stroke)] bg-white px-4 py-2 text-sm focus:border-[var(--primary-blue)] focus:outline-none disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-sm font-semibold uppercase tracking-[0.2em] text-white transition disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </aside>
  );
};
