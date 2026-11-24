import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import Login from "./Login";
import { HR_MANAGER_LOGIN_URL } from "../../config/hrManager";

describe("Login page", () => {
  it("redirects HERA sign-in to the shared HR portal", () => {
    const redirect = vi.fn();

    render(<Login redirect={redirect} />);

    expect(redirect).toHaveBeenCalledWith(HR_MANAGER_LOGIN_URL);
    expect(screen.getByRole("link", { name: /open the shared hr portal/i })).toHaveAttribute(
      "href",
      HR_MANAGER_LOGIN_URL,
    );
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });
});
