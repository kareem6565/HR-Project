import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Login from "./Login";

const mockNavigate = vi.fn();
const mockLogin = vi.fn();
let mockAuthState = { login: mockLogin, isAuthenticated: false, status: "unauthenticated" };

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("../../hooks/useAuth", () => ({
  default: () => mockAuthState,
}));

describe("Login page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuthState = { login: mockLogin, isAuthenticated: false, status: "unauthenticated" };
  });

  it("renders HERA login form fields", () => {
    render(<Login />);

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("submits credentials via useAuth login and redirects to dashboard on success", async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValueOnce({ id: "u1" });

    render(<Login />);

    await user.type(screen.getByLabelText(/email/i), "admin@test.com");
    await user.type(screen.getByLabelText(/password/i), "Password123!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({ email: "admin@test.com", password: "Password123!" });
    });
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/dashboard", { replace: true });
    });
  });

  it("shows loading state while authentication is in progress", async () => {
    const user = userEvent.setup();
    let resolveLogin;
    mockLogin.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveLogin = resolve;
        }),
    );

    render(<Login />);

    await user.type(screen.getByLabelText(/email/i), "admin@test.com");
    await user.type(screen.getByLabelText(/password/i), "Password123!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(screen.getByRole("button", { name: /signing in/i })).toBeDisabled();
    expect(screen.getByLabelText(/email/i)).toBeDisabled();

    resolveLogin({ id: "u1" });
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/dashboard", { replace: true }));
  });

  it("displays a clear error message when authentication fails", async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValueOnce({ response: { data: { detail: "Invalid email or password." } } });

    render(<Login />);

    await user.type(screen.getByLabelText(/email/i), "admin@test.com");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
    expect(screen.getByRole("button", { name: /sign in/i })).toBeEnabled();
  });
});
