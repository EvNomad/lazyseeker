import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { STUB_JOB } from "./mocks/handlers";
import JobDetailView from "../views/JobDetailView";

function renderDetail(id = "job-1") {
  return render(
    <MemoryRouter initialEntries={[`/jobs/${id}`]}>
      <Routes>
        <Route path="/jobs/:id" element={<JobDetailView />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("JobDetailView", () => {
  it("renders loading state initially", () => {
    renderDetail();
    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  it("renders job title and description after load", async () => {
    renderDetail();
    await waitFor(() => expect(screen.getByTestId("job-detail")).toBeInTheDocument());
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText(/Python experience/i)).toBeInTheDocument();
  });

  it("renders score breakdown panel when score_breakdown present", async () => {
    renderDetail();
    await waitFor(() => expect(screen.getByTestId("score-breakdown")).toBeInTheDocument());
  });

  it("renders error on 404", async () => {
    server.use(http.get("http://localhost:8000/jobs/:id", () =>
      HttpResponse.json({ detail: "Not found" }, { status: 404 })
    ));
    renderDetail("missing");
    await waitFor(() => expect(screen.getByTestId("error")).toBeInTheDocument());
  });

  it("shows tailor CV button", async () => {
    renderDetail();
    await waitFor(() => expect(screen.getByTestId("tailor-btn")).toBeInTheDocument());
  });
});
