import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { STUB_SUGGESTION } from "./mocks/handlers";
import SuggestionsView from "../views/SuggestionsView";

function renderSuggestions(id = "job-1") {
  return render(
    <MemoryRouter initialEntries={[`/jobs/${id}/suggestions`]}>
      <Routes>
        <Route path="/jobs/:id/suggestions" element={<SuggestionsView />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("SuggestionsView", () => {
  it("renders loading state initially", () => {
    renderSuggestions();
    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  it("renders suggestion cards after load", async () => {
    renderSuggestions();
    await waitFor(() => expect(screen.getByTestId("suggestion-list")).toBeInTheDocument());
    expect(screen.getByTestId(`suggestion-${STUB_SUGGESTION.id}`)).toBeInTheDocument();
  });

  it("shows original and suggested text", async () => {
    renderSuggestions();
    await waitFor(() => expect(screen.getByTestId("original-text")).toBeInTheDocument());
    expect(screen.getByTestId("suggested-text")).toBeInTheDocument();
  });

  it("export button disabled when no approved suggestions", async () => {
    renderSuggestions();
    await waitFor(() => expect(screen.getByTestId("export-btn")).toBeInTheDocument());
    expect(screen.getByTestId("export-btn")).toBeDisabled();
  });

  it("shows empty state when no suggestions", async () => {
    server.use(http.get("http://localhost:8000/jobs/:id/suggestions", () =>
      HttpResponse.json({ suggestions: [], cv_version_current: "abc" })
    ));
    renderSuggestions();
    await waitFor(() => expect(screen.getByTestId("empty-state")).toBeInTheDocument());
  });

  it("shows cv mismatch warning when cv_version differs", async () => {
    server.use(http.get("http://localhost:8000/jobs/:id/suggestions", () =>
      HttpResponse.json({
        suggestions: [{ ...STUB_SUGGESTION, cv_version: "old_version" }],
        cv_version_current: "new_version",
      })
    ));
    renderSuggestions();
    await waitFor(() => expect(screen.getByTestId("cv-mismatch-warning")).toBeInTheDocument());
  });
});
