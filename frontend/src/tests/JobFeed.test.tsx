import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import JobFeedView from "../views/JobFeedView";

function renderFeed() {
  return render(
    <MemoryRouter>
      <JobFeedView />
    </MemoryRouter>
  );
}

describe("JobFeedView", () => {
  it("renders loading state initially", () => {
    renderFeed();
    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  it("renders job cards after load", async () => {
    renderFeed();
    await waitFor(() => expect(screen.getByTestId("job-list")).toBeInTheDocument());
    expect(screen.getAllByTestId(/^job-card-/)).toHaveLength(3);
  });

  it("shows job titles", async () => {
    renderFeed();
    await waitFor(() => expect(screen.getByText("Backend Engineer")).toBeInTheDocument());
    expect(screen.getByText("Frontend Developer")).toBeInTheDocument();
  });

  it("shows empty state when no jobs returned", async () => {
    server.use(http.get("http://localhost:8000/jobs", () => HttpResponse.json([])));
    renderFeed();
    await waitFor(() => expect(screen.getByTestId("empty-state")).toBeInTheDocument());
  });

  it("shows error state on API failure", async () => {
    server.use(
      http.get("http://localhost:8000/jobs", () =>
        HttpResponse.json({ detail: "Server error" }, { status: 500 })
      )
    );
    renderFeed();
    await waitFor(() => expect(screen.getByTestId("error")).toBeInTheDocument());
  });

  it("shows job count", async () => {
    renderFeed();
    await waitFor(() => expect(screen.getByText("3 jobs")).toBeInTheDocument());
  });
});
