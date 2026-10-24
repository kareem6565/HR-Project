import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import Login, { getSafeRedirect } from "./Login";
import { AuthContext } from "../../context/AuthContext";

describe("Login component and safe redirection", () => {
  describe("getSafeRedirect open-redirect mitigation", () => {
    it("permits safe internal relative paths", () => {
      expect(getSafeRedirect("/jobs")).toBe("/jobs");
      expect(getSafeRedirect("/candidates/123")).toBe("/candidates/123");
      expect(getSafeRedirect({ pathname: "/evaluations", search: "?filter=all" })).toBe(
        "/evaluations?filter=all"
      );
    });

    it("rejects protocol-relative open-redirect URLs", () => {
      expect(getSafeRedirect("//evil.com/steal")).toBe("/dashboard");
      expect(getSafeRedirect("/\\evil.com")).toBe("/dashboard");
    });

    it("rejects absolute external URLs", () => {
      expect(getSafeRedirect("https://malicious.com")).toBe("/dashboard");
      expect(getSafeRedirect("http://phishing.site")).toBe("/dashboard");
      expect(getSafeRedirect("javascript:alert(1)")).toBe("/dashboard");
    });

    it("falls back to default destination when target is absent or invalid", () => {
      expect(getSafeRedirect(null)).toBe("/dashboard");
      expect(getSafeRedirect(undefined)).toBe("/dashboard");
      expect(getSafeRedirect(123)).toBe("/dashboard");
    });
  });

  describe("UI rendering and interaction", () => {
    let mockLogin;

    const renderLogin = (contextOverrides = {}) => {
      mockLogin = vi.fn();
      const defaultContext = {
        isAuthenticated: false,
        login: mockLogin,
        user: null,
        status: "unauthenticated",
        ...contextOverrides,
      };

      return render(
        <AuthContext.Provider value={defaultContext}>
          <MemoryRouter initialEntries={["/login"]}>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard</div>} />
            </Routes>
          </MemoryRouter>
        </AuthContext.Provider>
      );
    };

    it("renders email and password inputs with accessible labels", () => {
      renderLogin();
      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    });

    it("redirects to /dashboard immediately if already authenticated", () => {
      renderLogin({ isAuthenticated: true });
      expect(screen.getByTestId("dashboard")).toBeInTheDocument();
    });

    it("shows validation error when submitting with empty credentials", async () => {
      const user = userEvent.setup();
      renderLogin();

      await user.click(screen.getByRole("button", { name: /sign in/i }));
      expect(
        await screen.findByText(/please enter both email and password/i)
      ).toBeInTheDocument();
      expect(mockLogin).not.toHaveBeenCalled();
    });

    it("calls login with credentials and navigates on success", async () => {
      const user = userEvent.setup();
      renderLogin();

      mockLogin.mockResolvedValueOnce({
        user: { email: "recruiter@example.com", role: "recruiter" },
      });

      await user.type(screen.getByLabelText(/email address/i), "recruiter@example.com");
      await user.type(screen.getByLabelText(/password/i), "Secret123!");
      await user.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith({
          email: "recruiter@example.com",
          password: "Secret123!",
        });
      });
      expect(await screen.findByTestId("dashboard")).toBeInTheDocument();
    });

    it("displays generic failure message on 401 to prevent enumeration", async () => {
      const user = userEvent.setup();
      renderLogin();

      const err = new Error("Unauthorized");
      err.response = { status: 401, data: { detail: "Invalid email or password." } };
      mockLogin.mockRejectedValueOnce(err);

      await user.type(screen.getByLabelText(/email address/i), "wrong@example.com");
      await user.type(screen.getByLabelText(/password/i), "WrongPassword!");
      await user.click(screen.getByRole("button", { name: /sign in/i }));

      expect(
        await screen.findByText(/invalid email or password/i)
      ).toBeInTheDocument();
    });

    it("displays connection error message on server or network error", async () => {
      const user = userEvent.setup();
      renderLogin();

      const err = new Error("Network Error");
      mockLogin.mockRejectedValueOnce(err);

      await user.type(screen.getByLabelText(/email address/i), "admin@example.com");
      await user.type(screen.getByLabelText(/password/i), "ValidPassword123!");
      await user.click(screen.getByRole("button", { name: /sign in/i }));

      expect(
        await screen.findByText(/unable to connect to the authentication server/i)
      ).toBeInTheDocument();
    });
  });
});
