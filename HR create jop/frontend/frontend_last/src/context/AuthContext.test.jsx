import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider } from "./AuthContext";
import useAuth from "../hooks/useAuth";
import * as authService from "../services/authService";
import * as authStorage from "../services/authStorage";

// Test component exposing AuthContext values and actions
function TestConsumer() {
  const { status, user, error, isAuthenticated, isAdmin, isRecruiter, isHROperations, login, loginWithHRAssertion, logout } = useAuth();
  return (
    <div>
      <div data-testid="status">{status}</div>
      <div data-testid="is-authenticated">{String(isAuthenticated)}</div>
      <div data-testid="is-admin">{String(isAdmin)}</div>
      <div data-testid="is-recruiter">{String(isRecruiter)}</div>
      <div data-testid="is-hr-operations">{String(isHROperations)}</div>
      <div data-testid="user-email">{user?.email || "none"}</div>
      <div data-testid="user-role">{user?.role || "none"}</div>
      <div data-testid="error-message">{error || "none"}</div>
      <button
        onClick={() =>
          login({ email: "admin@test.com", password: "Password123!" }).catch(() => {})
        }
      >
        Trigger Login
      </button>
      <button onClick={logout}>Trigger Logout</button>
      <button onClick={() => loginWithHRAssertion("signed-hr-assertion").catch(() => {})}>
        Trigger HR SSO
      </button>
    </div>
  );
}

describe("AuthContext lifecycle and session management", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("initializes as unauthenticated when no token is present in sessionStorage", async () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated");
    });
    expect(screen.getByTestId("is-authenticated").textContent).toBe("false");
    expect(screen.getByTestId("user-email").textContent).toBe("none");
  });

  it("restores session on page reload when valid token is in sessionStorage", async () => {
    authStorage.setToken("saved-access-token");

    vi.spyOn(authService, "getCurrentUser").mockResolvedValueOnce({
      id: "user-123",
      email: "admin@company.com",
      full_name: "Admin Person",
      role: "admin",
      organization_id: "org-456",
      is_active: true,
      status: "active",
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("authenticated");
    });
    expect(screen.getByTestId("is-authenticated").textContent).toBe("true");
    expect(screen.getByTestId("is-admin").textContent).toBe("true");
    expect(screen.getByTestId("is-recruiter").textContent).toBe("false");
    expect(screen.getByTestId("is-hr-operations").textContent).toBe("false");
    expect(screen.getByTestId("user-email").textContent).toBe("admin@company.com");
  });

  it("clears token and marks unauthenticated when stored token is expired/revoked (401)", async () => {
    authStorage.setToken("expired-access-token");

    const err = new Error("Unauthorized");
    err.response = { status: 401 };
    vi.spyOn(authService, "getCurrentUser").mockRejectedValueOnce(err);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated");
    });
    expect(authStorage.getToken()).toBeNull();
    expect(screen.getByTestId("is-authenticated").textContent).toBe("false");
  });

  it("restores both workspace roles from the authenticated profile", async () => {
    authStorage.setToken("saved-access-token");
    vi.spyOn(authService, "getCurrentUser").mockResolvedValueOnce({
      id: "user-hera-hr",
      email: "hrm.hr001@sso.hera.local",
      full_name: "Hera HR User",
      role: "recruiter",
      roles: ["recruiter", "hr_operations"],
      organization_id: "org-456",
      is_active: true,
      status: "active",
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("authenticated");
    });
    expect(screen.getByTestId("is-recruiter").textContent).toBe("true");
    expect(screen.getByTestId("is-hr-operations").textContent).toBe("true");
  });

  it("clears a prior recruitment session before exchanging a new HR assertion", async () => {
    const user = userEvent.setup();
    authStorage.setToken("previous-user-token");
    vi.spyOn(authService, "getCurrentUser").mockResolvedValueOnce({
      id: "previous-user",
      email: "previous@company.com",
      role: "recruiter",
    });
    vi.spyOn(authService, "exchangeHRSsoAssertion").mockImplementationOnce(async () => {
      expect(authStorage.getToken()).toBeNull();
      authStorage.setToken("new-hr-token");
      return {
        access_token: "new-hr-token",
        user: {
          id: "hr-user",
          email: "hrm.hr001@sso.hera.local",
          role: "recruiter",
          roles: ["recruiter", "hr_operations"],
        },
      };
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("authenticated");
    });
    await user.click(screen.getByRole("button", { name: /trigger hr sso/i }));

    await waitFor(() => {
      expect(screen.getByTestId("user-email").textContent).toBe("hrm.hr001@sso.hera.local");
    });
    expect(authStorage.getToken()).toBe("new-hr-token");
  });

  it("transitions to unavailable and retains recoverable error when backend is down", async () => {
    authStorage.setToken("valid-token");

    const netErr = new Error("Connection Refused");
    vi.spyOn(authService, "getCurrentUser").mockRejectedValueOnce(netErr);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("unavailable");
    });
    // Does NOT silently treat user as authenticated
    expect(screen.getByTestId("is-authenticated").textContent).toBe("false");
    expect(screen.getByTestId("error-message").textContent).toContain("temporarily unavailable");
    // Token is kept so user can retry when backend recovers
    expect(authStorage.getToken()).toBe("valid-token");
  });

  it("invalidates session and clears sessionStorage on logout", async () => {
    const user = userEvent.setup();
    authStorage.setToken("active-token");

    vi.spyOn(authService, "getCurrentUser").mockResolvedValueOnce({
      id: "u-1",
      email: "recruiter@test.com",
      role: "recruiter",
    });
    const logoutSpy = vi.spyOn(authService, "logout").mockResolvedValueOnce();

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("authenticated");
    });

    await user.click(screen.getByText("Trigger Logout"));

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated");
    });
    expect(logoutSpy).toHaveBeenCalledTimes(1);
    expect(authStorage.getToken()).toBeNull();
    expect(screen.getByTestId("is-authenticated").textContent).toBe("false");
  });

  it("clears local token and resets state even if backend logout call fails", async () => {
    const user = userEvent.setup();
    authStorage.setToken("active-token");

    vi.spyOn(authService, "getCurrentUser").mockResolvedValueOnce({
      id: "u-1",
      email: "recruiter@test.com",
      role: "recruiter",
    });
    vi.spyOn(authService, "logout").mockRejectedValueOnce(new Error("Network Error"));

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("authenticated");
    });

    await user.click(screen.getByText("Trigger Logout"));

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated");
    });
    expect(authStorage.getToken()).toBeNull();
  });

  it("removes legacy hera.devIdentity from localStorage when setting token", () => {
    localStorage.setItem("hera.devIdentity", JSON.stringify({ userId: "legacy" }));
    expect(localStorage.getItem("hera.devIdentity")).not.toBeNull();

    authStorage.setToken("new-token");
    expect(localStorage.getItem("hera.devIdentity")).toBeNull();
  });
});
