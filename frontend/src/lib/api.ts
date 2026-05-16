// API client shared across the frontend. All requests carry the session cookie via
// `credentials: "include"`. In container mode the frontend is served same-origin so
// API_BASE is "" (relative paths); in dev mode point NEXT_PUBLIC_API_BASE at the
// backend (e.g. http://localhost:8000).
import type { BoardData } from "@/lib/kanban";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
}

export async function login(username: string, password: string): Promise<void> {
  const response = await apiFetch("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  if (response.status === 401) {
    throw new ApiError(401, "Invalid username or password.");
  }
  if (!response.ok) {
    throw new ApiError(response.status, "Login failed. Try again.");
  }
}

export async function logout(): Promise<void> {
  const response = await apiFetch("/api/auth/logout", { method: "POST" });
  if (!response.ok) {
    throw new ApiError(response.status, "Logout failed.");
  }
}

export type Me = { user: string };

export async function getMe(): Promise<Me | null> {
  const response = await apiFetch("/api/auth/me");
  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new ApiError(response.status, "Auth check failed.");
  }
  return (await response.json()) as Me;
}

export async function getBoard(): Promise<BoardData> {
  const response = await apiFetch("/api/board");
  if (!response.ok) {
    throw new ApiError(response.status, "Failed to load the board.");
  }
  return (await response.json()) as BoardData;
}

export async function updateBoard(data: BoardData): Promise<BoardData> {
  const response = await apiFetch("/api/board", {
    method: "PUT",
    body: JSON.stringify(data),
  });
  if (response.status === 422) {
    throw new ApiError(422, "The board update was rejected by the server.");
  }
  if (!response.ok) {
    throw new ApiError(response.status, "Failed to save the board.");
  }
  return (await response.json()) as BoardData;
}
