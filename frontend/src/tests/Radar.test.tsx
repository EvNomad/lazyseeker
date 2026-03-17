import { describe, it, expect } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { STUB_CRAWL_LOG_ENTRY } from "./mocks/handlers";
import RadarView from "../views/RadarView";

function renderRadar() {
  return render(<RadarView />);
}

describe("RadarView", () => {
  it("renders loading state initially", () => {
    renderRadar();
    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  it("renders run button after load", async () => {
    renderRadar();
    await waitFor(() => expect(screen.getByTestId("radar-view")).toBeInTheDocument());
    expect(screen.getByTestId("run-btn")).toBeInTheDocument();
  });

  it("shows crawl log entries", async () => {
    server.use(
      http.get("http://localhost:8000/radar/log", () =>
        HttpResponse.json([STUB_CRAWL_LOG_ENTRY])
      )
    );
    renderRadar();
    await waitFor(() => expect(screen.getByTestId("crawl-log")).toBeInTheDocument());
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("success")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("shows in progress message on 409", async () => {
    server.use(
      http.post("http://localhost:8000/radar/run", () =>
        HttpResponse.json({ detail: "Crawl already running" }, { status: 409 })
      )
    );
    renderRadar();
    await waitFor(() => expect(screen.getByTestId("run-btn")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("run-btn"));
    await waitFor(() => expect(screen.getByText("Crawl in progress...")).toBeInTheDocument());
  });
});
