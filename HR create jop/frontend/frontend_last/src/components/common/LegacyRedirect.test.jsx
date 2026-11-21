import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import LegacyRedirect from "./LegacyRedirect";

function PathProbe() {
  const { pathname, search, hash } = useLocation();
  return <span data-testid="path">{`${pathname}${search}${hash}`}</span>;
}

describe("legacy route redirects", () => {
  it("redirects to the canonical route and preserves query and hash", async () => {
    render(
      <MemoryRouter initialEntries={["/matching?jobId=job-1#candidate"]}>
        <Routes>
          <Route
            path="/matching"
            element={<LegacyRedirect to="/matching-results" />}
          />
          <Route path="/matching-results" element={<PathProbe />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByTestId("path")).toHaveTextContent(
      "/matching-results?jobId=job-1#candidate"
    );
  });

  it("redirects the legacy evaluations URL to applications", async () => {
    render(
      <MemoryRouter initialEntries={["/evaluations"]}>
        <Routes>
          <Route
            path="/evaluations"
            element={<LegacyRedirect to="/applications" />}
          />
          <Route path="/applications" element={<h1>All Applications</h1>} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "All Applications" })).toBeInTheDocument();
  });
});
