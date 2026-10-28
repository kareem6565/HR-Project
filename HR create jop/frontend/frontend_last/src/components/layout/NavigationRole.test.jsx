import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./Sidebar";
import Navbar from "./Navbar";
import ProtectedRoute from "../common/ProtectedRoute";
import { AuthContext } from "../../context/AuthContext";

describe("HERA UI-09: Simplified MVP Navigation and Role-Aware Controls", () => {
  const renderSidebar = (role, initialEntries = ["/dashboard"]) => {
    const isAdmin = role === "admin" || role === "administrator";
    const isRecruiter = role === "recruiter";
    const authValues = {
      status: "authenticated",
      isAuthenticated: true,
      isAdmin,
      isRecruiter,
      role,
      user: { id: "u-1", email: `${role || "unknown"}@company.com`, role },
      logout: vi.fn(),
      checkAuth: vi.fn(),
    };

    return render(
      <AuthContext.Provider value={authValues}>
        <MemoryRouter initialEntries={initialEntries}>
          <Sidebar />
        </MemoryRouter>
      </AuthContext.Provider>
    );
  };

  describe("Primary MVP Workflow Links", () => {
    it("renders primary MVP navigation items (Jobs, Screening, Matching, Candidates, Applications)", () => {
      renderSidebar("recruiter");

      expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/dashboard");
      expect(screen.getByRole("link", { name: "Jobs" })).toHaveAttribute("href", "/jobs");
      expect(screen.getByRole("link", { name: "Screening" })).toHaveAttribute("href", "/candidates/screen");
      expect(screen.getByRole("link", { name: "Matching Results" })).toHaveAttribute("href", "/matching-results");
      expect(screen.getByRole("link", { name: "Candidates" })).toHaveAttribute("href", "/candidates");
      expect(screen.getByRole("link", { name: "Applications" })).toHaveAttribute("href", "/applications");
    });

    it("renders grouped secondary operations (Interviews, Talent Pool, Analytics)", () => {
      renderSidebar("recruiter");

      expect(screen.getByRole("link", { name: "Interviews" })).toHaveAttribute("href", "/interviews");
      expect(screen.getByRole("link", { name: "Talent Pool" })).toHaveAttribute("href", "/talent-pool");
      expect(screen.getByRole("link", { name: "Analytics" })).toHaveAttribute("href", "/analytics");
    });

    it("does not render redundant /evaluations in sidebar navigation", () => {
      renderSidebar("recruiter");
      expect(screen.queryByRole("link", { name: /evaluations/i })).not.toBeInTheDocument();
    });
  });

  describe("Accessibility and Collapsed States", () => {
    it("provides accessible aria-label and title on all navigation links for collapsed screen-reader support", () => {
      renderSidebar("admin");

      const links = screen.getAllByRole("link");
      expect(links.length).toBeGreaterThan(0);

      links.forEach((link) => {
        expect(link).toHaveAttribute("aria-label");
        expect(link).toHaveAttribute("title");
        expect(link.getAttribute("aria-label")).toBe(link.getAttribute("title"));
      });
    });

    it("marks the active route with aria-current='page'", () => {
      renderSidebar("recruiter", ["/candidates/screen"]);

      const screeningLink = screen.getByRole("link", { name: "Screening" });
      expect(screeningLink).toHaveAttribute("aria-current", "page");
      expect(screeningLink.className).toContain("active");

      const jobsLink = screen.getByRole("link", { name: "Jobs" });
      expect(jobsLink).not.toHaveAttribute("aria-current", "page");
      expect(jobsLink.className).not.toContain("active");
    });

    it("does not mark Applications active for a nested application review route", () => {
      renderSidebar("recruiter", ["/applications/app-1/review"]);

      expect(screen.getByRole("link", { name: "Applications" })).not.toHaveAttribute("aria-current", "page");
      expect(screen.getByRole("link", { name: "Applications" }).className).not.toContain("active");
    });

    it("marks Screening without also activating the Candidates destination", () => {
      renderSidebar("recruiter", ["/candidates/screen"]);

      expect(screen.getByRole("link", { name: "Screening" })).toHaveAttribute("aria-current", "page");
      expect(screen.getByRole("link", { name: "Candidates" })).not.toHaveAttribute("aria-current", "page");
    });

    it("has accessible navigation container with clear landmark", () => {
      renderSidebar("recruiter");
      expect(screen.getByRole("navigation", { name: /main navigation/i })).toBeInTheDocument();
    });
  });

  describe("Role-based Navigation Visibility", () => {
    it("shows Settings but not the technical AI Activity page in navigation for 'admin' role", () => {
      renderSidebar("admin");
      expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
      expect(screen.queryByRole("link", { name: "AI Activity" })).not.toBeInTheDocument();
    });

    it("shows Settings but not the technical AI Activity page in navigation for 'administrator' role", () => {
      renderSidebar("administrator");
      expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
      expect(screen.queryByRole("link", { name: "AI Activity" })).not.toBeInTheDocument();
    });

    it("hides administrator controls for 'recruiter' role", () => {
      renderSidebar("recruiter");
      expect(screen.queryByRole("link", { name: /settings/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("link", { name: /ai activity/i })).not.toBeInTheDocument();
    });

    it("hides administrator controls for unknown or missing role", () => {
      renderSidebar("viewer");
      expect(screen.queryByRole("link", { name: /settings/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("link", { name: /ai activity/i })).not.toBeInTheDocument();
    });
  });

  describe("Direct Route Authorization Protection (ProtectedRoute)", () => {
    const renderDirectRoute = (role, path = "/settings") => {
      const isAdmin = role === "admin" || role === "administrator";
      const authValues = {
        status: "authenticated",
        isAuthenticated: true,
        isAdmin,
        isRecruiter: role === "recruiter",
        role,
        user: { id: "u-1", email: `${role}@company.com`, role },
        logout: vi.fn(),
        checkAuth: vi.fn(),
      };

      return render(
        <AuthContext.Provider value={authValues}>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route path="/dashboard" element={<div>Dashboard Page</div>} />
              <Route
                path="/ai-activity"
                element={
                  <ProtectedRoute allowedRoles={["admin", "administrator"]}>
                    <div>Technical AI Activity Content</div>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings"
                element={
                  <ProtectedRoute allowedRoles={["admin", "administrator"]}>
                    <div>Secret Admin Settings Content</div>
                  </ProtectedRoute>
                }
              />
            </Routes>
          </MemoryRouter>
        </AuthContext.Provider>
      );
    };

    it("allows administrator to directly access /settings", () => {
      renderDirectRoute("admin", "/settings");
      expect(screen.getByText("Secret Admin Settings Content")).toBeInTheDocument();
      expect(screen.queryByText(/access restricted/i)).not.toBeInTheDocument();
    });

    it("blocks recruiter from directly accessing /settings with access restricted message", () => {
      renderDirectRoute("recruiter", "/settings");
      expect(screen.queryByText("Secret Admin Settings Content")).not.toBeInTheDocument();
      expect(screen.getByText("Access Restricted")).toBeInTheDocument();
      expect(screen.getByText(/your account has the/i)).toHaveTextContent("recruiter");
      expect(screen.getByRole("link", { name: /return to dashboard/i })).toHaveAttribute("href", "/dashboard");
    });

    it("blocks unknown roles from directly accessing /settings", () => {
      renderDirectRoute("guest", "/settings");
      expect(screen.queryByText("Secret Admin Settings Content")).not.toBeInTheDocument();
      expect(screen.getByText("Access Restricted")).toBeInTheDocument();
      expect(screen.getByText(/your account has the/i)).toHaveTextContent("guest");
    });

    it("allows administrators and blocks recruiters on the direct AI Activity route", () => {
      const admin = renderDirectRoute("admin", "/ai-activity");
      expect(screen.getByText("Technical AI Activity Content")).toBeInTheDocument();
      admin.unmount();

      renderDirectRoute("recruiter", "/ai-activity");
      expect(screen.queryByText("Technical AI Activity Content")).not.toBeInTheDocument();
      expect(screen.getByText("Access Restricted")).toBeInTheDocument();
    });
  });

  describe("Navbar Identity and Session Controls", () => {
    it("displays user identity, role badge, and functional logout button", async () => {
      const userEventSetup = userEvent.setup();
      const mockLogout = vi.fn();
      const authValues = {
        status: "authenticated",
        isAuthenticated: true,
        user: {
          id: "u-100",
          full_name: "Sarah Recruiter",
          email: "sarah@company.com",
          role: "recruiter",
        },
        logout: mockLogout,
      };

      render(
        <AuthContext.Provider value={authValues}>
          <MemoryRouter>
            <Navbar pathname="/dashboard" />
          </MemoryRouter>
        </AuthContext.Provider>
      );

      expect(screen.getByText("Sarah Recruiter")).toBeInTheDocument();
      expect(screen.getByText("sarah@company.com")).toBeInTheDocument();
      expect(screen.getByText("recruiter")).toBeInTheDocument();

      const logoutBtn = screen.getByRole("button", { name: /sign out/i });
      expect(logoutBtn).toBeInTheDocument();

      await userEventSetup.click(logoutBtn);
      expect(mockLogout).toHaveBeenCalledTimes(1);
    });
  });
});
