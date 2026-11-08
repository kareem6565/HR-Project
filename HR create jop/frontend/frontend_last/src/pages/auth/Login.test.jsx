import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import Login from "./Login";
import { HR_MANAGER_WORKSPACE_URL } from "../../config/hrManager";

describe("HR Manager sign-in redirect", () => {
  it("redirects to the configured HR Manager workspace", async () => {
    const redirect = vi.fn();

    const { container } = render(<Login redirect={redirect} />);

    await waitFor(() => {
      expect(redirect).toHaveBeenCalledWith(HR_MANAGER_WORKSPACE_URL);
    });
    expect(container).toBeEmptyDOMElement();
  });

  it("does not render a separate recruitment login form", () => {
    const { queryByRole } = render(<Login redirect={vi.fn()} />);

    expect(queryByRole("textbox", { name: /email/i })).not.toBeInTheDocument();
    expect(queryByRole("button", { name: /sign in/i })).not.toBeInTheDocument();
  });
});
