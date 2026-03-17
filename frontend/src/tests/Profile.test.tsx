import { describe, it, expect } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { STUB_PROFILE } from "./mocks/handlers";
import ProfileView from "../views/ProfileView";

function renderProfile() {
  return render(<ProfileView />);
}

describe("ProfileView", () => {
  it("renders loading state initially", () => {
    renderProfile();
    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  it("renders cv textarea with profile data", async () => {
    renderProfile();
    await waitFor(() => expect(screen.getByTestId("profile-view")).toBeInTheDocument());
    const textarea = screen.getByTestId("cv-textarea") as HTMLTextAreaElement;
    expect(textarea.value).toBe(STUB_PROFILE.cv_markdown);
  });

  it("save button submits profile", async () => {
    renderProfile();
    await waitFor(() => expect(screen.getByTestId("save-btn")).toBeInTheDocument());

    server.use(
      http.put("http://localhost:8000/profile", () =>
        HttpResponse.json({ ...STUB_PROFILE, cv_markdown: "# Updated CV" })
      )
    );

    fireEvent.click(screen.getByTestId("save-btn"));
    await waitFor(() => expect(screen.getByTestId("save-success")).toBeInTheDocument());
  });
});
