import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import EvaluationsList from "./EvaluationsList";

function PathProbe() {
  return <span data-testid="path">{useLocation().pathname}</span>;
}

describe("legacy evaluations route", () => {
  it("redirects to the application-level review queue", async () => {
    render(
      <MemoryRouter initialEntries={["/evaluations"]}>
        <Routes>
          <Route path="/evaluations" element={<EvaluationsList />} />
          <Route path="/applications" element={<h1>All Applications</h1>} />
        </Routes>
        <PathProbe />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "All Applications" })).toBeInTheDocument();
    expect(screen.getByTestId("path")).toHaveTextContent("/applications");
  });
});
