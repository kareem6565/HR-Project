import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import ProtectedRoute from "./ProtectedRoute";
import { AuthContext } from "../../context/AuthContext";

describe("ProtectedRoute component", () => {
  const renderWithAuth = (authValues, allowedRoles = undefined) => {
    return render(
      <AuthContext.Provider value={authValues}>
        <MemoryRouter initialEntries={["/protected"]}>
          <Routes>
            <Route
              path="/protected"
              element={
                <ProtectedRoute allowedRoles={allowedRoles}>
                  <div data-testid="sensitive-data">Confidential Candidate Information</div>
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<div data-testid="login-page">Login Page</div>} />
            <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard</div>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    );
  };

  it("renders loading spinner and hides sensitive data while initializing", () => {
    renderWithAuth({
      status: "initializing",
      user: null,
      error: null,
      checkAuth: vi.fn(),
    });

    expect(screen.getByText(/authenticating\.\.\./i)).toBeInTheDocument();
    expect(screen.queryByTestId("sensitive-data")).not.toBeInTheDocument();
  });

  it("redirects unauthenticated users to /login and hides sensitive data", () => {
    renderWithAuth({
      status: "unauthenticated",
      user: null,
      error: null,
      checkAuth: vi.fn(),
    });

    expect(screen.getByTestId("login-page")).toBeInTheDocument();
    expect(screen.queryByTestId("sensitive-data")).not.toBeInTheDocument();
  });

  it("renders recoverable error screen with retry button when service is unavailable", () => {
    const mockRetry = vi.fn();
    renderWithAuth({
      status: "unavailable",
      user: null,
      error: "Could not reach the server.",
      checkAuth: mockRetry,
    });

    expect(screen.getByText(/authentication unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/could not reach the server/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry connection/i })).toBeInTheDocument();
    expect(screen.queryByTestId("sensitive-data")).not.toBeInTheDocument();
  });

  it("renders protected content when user is authenticated with allowed role", () => {
    renderWithAuth(
      {
        status: "authenticated",
        user: { id: "u-1", email: "admin@test.com", role: "admin" },
        error: null,
      },
      ["admin"]
    );

    expect(screen.getByTestId("sensitive-data")).toBeInTheDocument();
  });

  it("renders access-denied message without logging out when user lacks required role", () => {
    renderWithAuth(
      {
        status: "authenticated",
        user: { id: "u-2", email: "recruiter@test.com", role: "recruiter" },
        error: null,
      },
      ["admin"]
    );

    // Shows 403 access restricted view
    expect(screen.getByText(/access restricted/i)).toBeInTheDocument();
    expect(screen.getByText(/this section is restricted to/i)).toBeInTheDocument();
    expect(screen.queryByTestId("sensitive-data")).not.toBeInTheDocument();
    expect(screen.queryByTestId("login-page")).not.toBeInTheDocument();
  });
});
