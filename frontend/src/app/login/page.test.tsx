import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, beforeEach, describe, it, expect } from "vitest";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: vi.fn(), back: vi.fn() }),
}));

const loginMock = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, login: (...args: unknown[]) => loginMock(...args) };
});

import LoginPage from "./page";
import { ApiError } from "@/lib/api";

describe("LoginPage", () => {
  beforeEach(() => {
    replaceMock.mockReset();
    loginMock.mockReset();
  });

  it("submits credentials and redirects on success", async () => {
    loginMock.mockResolvedValueOnce(undefined);

    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/username/i), "user");
    await userEvent.type(screen.getByLabelText(/password/i), "password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(loginMock).toHaveBeenCalledWith("user", "password");
    expect(replaceMock).toHaveBeenCalledWith("/");
  });

  it("shows the API error message and does not redirect on 401", async () => {
    loginMock.mockRejectedValueOnce(new ApiError(401, "Invalid username or password."));

    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/username/i), "user");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid username or password.",
    );
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("shows a generic error on network failure", async () => {
    loginMock.mockRejectedValueOnce(new TypeError("network down"));

    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/username/i), "user");
    await userEvent.type(screen.getByLabelText(/password/i), "password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/network error/i);
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
