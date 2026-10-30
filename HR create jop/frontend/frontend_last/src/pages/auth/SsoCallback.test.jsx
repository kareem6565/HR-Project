import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthContext } from "../../context/AuthContext";
import SsoCallback from "./SsoCallback";

describe("SsoCallback error guidance", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/sso/callback#assertion=test-assertion");
  });

  function renderCallback(error) {
    const loginWithHRAssertion = vi.fn().mockRejectedValue(error);
    render(
      <AuthContext.Provider value={{ isAuthenticated: false, loginWithHRAssertion }}>
        <MemoryRouter initialEntries={["/sso/callback"]}>
          <SsoCallback />
        </MemoryRouter>
      </AuthContext.Provider>
    );
    return loginWithHRAssertion;
  }

  it("explains how to resolve organization association failures", async () => {
    const error = new Error("Service unavailable");
    error.response = {
      status: 503,
      data: { detail: "The configured HERA organization does not exist." },
    };

    const login = renderCallback(error);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /ask your administrator to verify the organization setup/i
    );
    expect(login).toHaveBeenCalledWith("test-assertion");
  });

  it("explains when an HR account is not permitted to enter Recruitment", async () => {
    const error = new Error("Forbidden");
    error.response = { status: 403, data: { detail: "Forbidden" } };

    renderCallback(error);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /ask your hr administrator to review your account/i
    );
  });
});
