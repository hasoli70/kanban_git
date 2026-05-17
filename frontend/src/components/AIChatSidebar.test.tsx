import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  }
  return {
    chatAI: vi.fn(),
    ApiError,
  };
});

import { chatAI } from "@/lib/api";
import { AIChatSidebar } from "@/components/AIChatSidebar";

const renderOpen = (onBoardUpdated = vi.fn(), onClose = vi.fn()) => {
  render(
    <AIChatSidebar
      open={true}
      onClose={onClose}
      onBoardUpdated={onBoardUpdated}
    />,
  );
  return { onBoardUpdated, onClose };
};

describe("AIChatSidebar", () => {
  beforeEach(() => {
    vi.mocked(chatAI).mockReset();
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <AIChatSidebar
        open={false}
        onClose={vi.fn()}
        onBoardUpdated={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows an empty state hint when first opened", () => {
    renderOpen();
    expect(screen.getByText(/ask me to add a card/i)).toBeInTheDocument();
  });

  it("appends the user message and the assistant reply on send", async () => {
    vi.mocked(chatAI).mockResolvedValueOnce({
      reply: "You have zero cards.",
      board_updated: false,
      validation_error: null,
    });

    renderOpen();
    const input = screen.getByLabelText("Message");
    await userEvent.type(input, "How many cards?");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByText("How many cards?")).toBeInTheDocument();
    expect(await screen.findByText("You have zero cards.")).toBeInTheDocument();

    expect(chatAI).toHaveBeenCalledTimes(1);
    expect(vi.mocked(chatAI).mock.calls[0][0]).toBe("How many cards?");
    expect(vi.mocked(chatAI).mock.calls[0][1]).toEqual([]);
  });

  it("calls onBoardUpdated and shows a confirmation when the board changes", async () => {
    vi.mocked(chatAI).mockResolvedValueOnce({
      reply: "Added the card.",
      board_updated: true,
      validation_error: null,
    });

    const { onBoardUpdated } = renderOpen();
    await userEvent.type(screen.getByLabelText("Message"), "add card");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(onBoardUpdated).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/board updated/i)).toBeInTheDocument();
  });

  it("surfaces validation_error without calling onBoardUpdated", async () => {
    vi.mocked(chatAI).mockResolvedValueOnce({
      reply: "I tried but...",
      board_updated: false,
      validation_error: "column ids cannot change",
    });

    const { onBoardUpdated } = renderOpen();
    await userEvent.type(screen.getByLabelText("Message"), "rename col id");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(
      await screen.findByText(/update rejected: column ids cannot change/i),
    ).toBeInTheDocument();
    expect(onBoardUpdated).not.toHaveBeenCalled();
  });

  it("shows an error banner when the AI call fails", async () => {
    const { ApiError } = await import("@/lib/api");
    vi.mocked(chatAI).mockRejectedValueOnce(
      new ApiError(502, "The AI provider is unavailable. Try again later."),
    );

    renderOpen();
    await userEvent.type(screen.getByLabelText("Message"), "hi");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable/i);
  });

  it("sends the prior conversation as history on the next message", async () => {
    vi.mocked(chatAI)
      .mockResolvedValueOnce({
        reply: "first reply",
        board_updated: false,
        validation_error: null,
      })
      .mockResolvedValueOnce({
        reply: "second reply",
        board_updated: false,
        validation_error: null,
      });

    renderOpen();
    const input = screen.getByLabelText("Message");
    await userEvent.type(input, "first");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await screen.findByText("first reply");

    await userEvent.type(input, "second");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await screen.findByText("second reply");

    expect(chatAI).toHaveBeenCalledTimes(2);
    const secondCallHistory = vi.mocked(chatAI).mock.calls[1][1];
    expect(secondCallHistory).toEqual([
      { role: "user", content: "first" },
      { role: "assistant", content: "first reply" },
    ]);
  });

  it("calls onClose when the close button is clicked", async () => {
    const { onClose } = renderOpen();
    await userEvent.click(screen.getByRole("button", { name: /close chat/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
