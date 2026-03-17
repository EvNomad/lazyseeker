import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScoreBadge } from "../components/ScoreBadge";

function makeJob(overrides: Partial<{ overall_score: number | null; score_status: string; score_breakdown: string | null }>) {
  return {
    overall_score: null,
    score_status: "pending" as const,
    score_breakdown: null,
    ...overrides,
  } as Parameters<typeof ScoreBadge>[0]["job"];
}

describe("ScoreBadge", () => {
  it("renders green badge for score >= 80", () => {
    const { container } = render(<ScoreBadge job={makeJob({ overall_score: 82, score_status: "scored" })} />);
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(container.firstChild).toHaveClass("bg-green-100");
  });

  it("renders yellow badge for score 60-79", () => {
    const { container } = render(<ScoreBadge job={makeJob({ overall_score: 70, score_status: "scored" })} />);
    expect(screen.getByText("70")).toBeInTheDocument();
    expect(container.firstChild).toHaveClass("bg-yellow-100");
  });

  it("renders red badge for score < 60", () => {
    const { container } = render(<ScoreBadge job={makeJob({ overall_score: 45, score_status: "scored" })} />);
    expect(screen.getByText("45")).toBeInTheDocument();
    expect(container.firstChild).toHaveClass("bg-red-100");
  });

  it("renders pending badge when score is null", () => {
    const { container } = render(<ScoreBadge job={makeJob({ overall_score: null, score_status: "pending" })} />);
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(container.firstChild).toHaveClass("bg-gray-100");
  });

  it("renders error badge when score_status is error", () => {
    const { container } = render(<ScoreBadge job={makeJob({ overall_score: null, score_status: "error" })} />);
    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(container.firstChild).toHaveClass("bg-red-100");
  });

  it("renders amber badge for low_signal_jd", () => {
    const breakdown = JSON.stringify({ low_signal_jd: true });
    const { container } = render(
      <ScoreBadge job={makeJob({ overall_score: 65, score_status: "scored", score_breakdown: breakdown })} />
    );
    expect(screen.getByText("65~")).toBeInTheDocument();
    expect(container.firstChild).toHaveClass("bg-amber-100");
  });
});
