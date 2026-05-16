import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, beforeEach, describe, it, expect } from "vitest";

import type { BoardData } from "@/lib/kanban";

vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  }
  return {
    getBoard: vi.fn(),
    updateBoard: vi.fn(),
    getMe: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    ApiError,
  };
});

import { getBoard, updateBoard } from "@/lib/api";
import { KanbanBoard } from "@/components/KanbanBoard";

const makeEmptyBoard = (): BoardData => ({
  columns: [
    { id: "col-backlog", title: "Backlog", cardIds: [] },
    { id: "col-discovery", title: "Discovery", cardIds: [] },
    { id: "col-progress", title: "In Progress", cardIds: [] },
    { id: "col-review", title: "Review", cardIds: [] },
    { id: "col-done", title: "Done", cardIds: [] },
  ],
  cards: {},
});

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];

describe("KanbanBoard", () => {
  beforeEach(() => {
    vi.mocked(getBoard).mockReset();
    vi.mocked(updateBoard).mockReset();
    vi.mocked(getBoard).mockResolvedValue(makeEmptyBoard());
    vi.mocked(updateBoard).mockResolvedValue(makeEmptyBoard());
  });

  it("shows loading then renders five columns from the backend", async () => {
    render(<KanbanBoard />);
    expect(screen.getByText(/loading board/i)).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getAllByTestId(/column-/i)).toHaveLength(5),
    );
    expect(getBoard).toHaveBeenCalledTimes(1);
  });

  it("renames a column and calls updateBoard after the debounce", async () => {
    render(<KanbanBoard />);
    await waitFor(() =>
      expect(screen.getAllByTestId(/column-/i)).toHaveLength(5),
    );

    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "Idee");
    expect(input).toHaveValue("Idee");

    // Not called yet (debounced). Wait past the debounce window.
    expect(updateBoard).not.toHaveBeenCalled();
    await waitFor(
      () => expect(updateBoard).toHaveBeenCalledTimes(1),
      { timeout: 1500 },
    );
    const lastCall = vi.mocked(updateBoard).mock.calls.at(-1);
    expect(lastCall?.[0].columns[0].title).toBe("Idee");
  });

  it("adds a card optimistically and persists it", async () => {
    render(<KanbanBoard />);
    await waitFor(() =>
      expect(screen.getAllByTestId(/column-/i)).toHaveLength(5),
    );

    const column = getFirstColumn();
    await userEvent.click(
      within(column).getByRole("button", { name: /add a card/i }),
    );
    await userEvent.type(
      within(column).getByPlaceholderText(/card title/i),
      "New card",
    );
    await userEvent.type(
      within(column).getByPlaceholderText(/details/i),
      "Notes",
    );
    await userEvent.click(
      within(column).getByRole("button", { name: /add card/i }),
    );

    expect(within(column).getByText("New card")).toBeInTheDocument();
    await waitFor(() => expect(updateBoard).toHaveBeenCalledTimes(1));

    const deleteButton = within(column).getByRole("button", {
      name: /delete new card/i,
    });
    await userEvent.click(deleteButton);
    expect(within(column).queryByText("New card")).not.toBeInTheDocument();
    await waitFor(() => expect(updateBoard).toHaveBeenCalledTimes(2));
  });

  it("rolls back to the last saved state and shows an error when the save fails", async () => {
    const initial = makeEmptyBoard();
    vi.mocked(getBoard).mockResolvedValueOnce(initial);
    vi.mocked(updateBoard).mockRejectedValueOnce(new Error("network down"));

    render(<KanbanBoard />);
    await waitFor(() =>
      expect(screen.getAllByTestId(/column-/i)).toHaveLength(5),
    );

    const column = getFirstColumn();
    await userEvent.click(
      within(column).getByRole("button", { name: /add a card/i }),
    );
    await userEvent.type(
      within(column).getByPlaceholderText(/card title/i),
      "Doomed card",
    );
    await userEvent.click(
      within(column).getByRole("button", { name: /add card/i }),
    );

    // After the rejected save resolves, board is rolled back and an error banner appears
    await waitFor(() =>
      expect(within(column).queryByText("Doomed card")).not.toBeInTheDocument(),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(/save/i);
  });

  it("shows the load error banner when getBoard fails", async () => {
    vi.mocked(getBoard).mockRejectedValueOnce(new Error("offline"));
    render(<KanbanBoard />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /couldn't load the board/i,
    );
  });
});
