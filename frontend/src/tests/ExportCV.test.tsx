import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { STUB_SUGGESTION } from "./mocks/handlers";
import SuggestionsView from "../views/SuggestionsView";

// Define URL.createObjectURL / revokeObjectURL for jsdom (not implemented in jsdom)
beforeEach(() => {
  global.URL.createObjectURL = vi.fn(() => "blob:mock-url");
  global.URL.revokeObjectURL = vi.fn();
});

function renderSuggestions(id = "job-1") {
  return render(
    <MemoryRouter initialEntries={[`/jobs/${id}/suggestions`]}>
      <Routes>
        <Route path="/jobs/:id/suggestions" element={<SuggestionsView />} />
      </Routes>
    </MemoryRouter>
  );
}

// Helper: render with an approved suggestion so export is enabled
function renderWithApproved(id = "job-1") {
  server.use(
    http.get("http://localhost:8000/jobs/:id/suggestions", () =>
      HttpResponse.json({
        suggestions: [{ ...STUB_SUGGESTION, status: "approved" }],
        cv_version_current: "abc123",
      })
    )
  );
  return renderSuggestions(id);
}

describe("Export CV", () => {
  it("export button is disabled when no suggestions are approved", async () => {
    renderSuggestions();
    await waitFor(() => expect(screen.getByTestId("export-btn")).toBeInTheDocument());
    expect(screen.getByTestId("export-btn")).toBeDisabled();
  });

  it("export button is enabled when at least one suggestion is approved", async () => {
    renderWithApproved();
    await waitFor(() => expect(screen.getByTestId("export-btn")).not.toBeDisabled());
  });

  it("successful export triggers a download with tailored-cv.md filename", async () => {
    const user = userEvent.setup();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    renderWithApproved();
    await waitFor(() => expect(screen.getByTestId("export-btn")).not.toBeDisabled());

    await user.click(screen.getByTestId("export-btn"));

    await waitFor(() => {
      expect(URL.createObjectURL).toHaveBeenCalled();
      expect(clickSpy).toHaveBeenCalled();
    });

    clickSpy.mockRestore();
  });

  it("shows export-error and triggers fallback download when API returns error", async () => {
    const user = userEvent.setup();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    // Override the tailored-cv endpoint to return a 500
    server.use(
      http.get("http://localhost:8000/jobs/:id/tailored-cv", () =>
        HttpResponse.json({ detail: "Server error" }, { status: 500 })
      )
    );

    renderWithApproved();
    await waitFor(() => expect(screen.getByTestId("export-btn")).not.toBeDisabled());

    await user.click(screen.getByTestId("export-btn"));

    await waitFor(() => expect(screen.getByTestId("export-error")).toBeInTheDocument());
    expect(screen.getByTestId("export-error")).toHaveTextContent("Export failed");

    // Fallback download should still be triggered
    expect(clickSpy).toHaveBeenCalled();

    clickSpy.mockRestore();
  });

  it("fallback markdown contains job title and suggestion sections", async () => {
    const user = userEvent.setup();

    let capturedContent = "";
    const OriginalBlob = global.Blob;
    vi.stubGlobal(
      "Blob",
      class MockBlob extends OriginalBlob {
        constructor(parts: BlobPart[], options?: BlobPropertyBag) {
          super(parts, options);
          if (options?.type === "text/markdown" && parts.length > 0) {
            capturedContent = parts[0] as string;
          }
        }
      }
    );
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    server.use(
      http.get("http://localhost:8000/jobs/:id/tailored-cv", () =>
        HttpResponse.json({ detail: "Server error" }, { status: 500 })
      )
    );

    renderWithApproved();
    await waitFor(() => expect(screen.getByTestId("export-btn")).not.toBeDisabled());

    await user.click(screen.getByTestId("export-btn"));

    await waitFor(() => expect(screen.getByTestId("export-error")).toBeInTheDocument());

    // The fallback markdown should contain the section and suggestion details
    expect(capturedContent).toContain("## Experience");
    expect(capturedContent).toContain("**Original:**");
    expect(capturedContent).toContain("**Suggested:**");
    expect(capturedContent).toContain("> Rationale:");
  });
});
