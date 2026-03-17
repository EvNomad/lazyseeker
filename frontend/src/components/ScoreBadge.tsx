import type { JobPosting, ScoreBreakdown } from "../api/types";

interface Props {
  job: Pick<JobPosting, "overall_score" | "score_status" | "score_breakdown">;
}

export function ScoreBadge({ job }: Props) {
  if (job.score_status === "error") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
        Error
      </span>
    );
  }

  if (job.overall_score === null || job.score_status === "pending") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
        Pending
      </span>
    );
  }

  let isLowSignal = false;
  if (job.score_breakdown) {
    try {
      const breakdown: ScoreBreakdown = JSON.parse(job.score_breakdown);
      isLowSignal = breakdown.low_signal_jd;
    } catch {
      // ignore malformed JSON
    }
  }

  if (isLowSignal) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
        {job.overall_score}~
      </span>
    );
  }

  const score = job.overall_score;
  const colorClass =
    score >= 80
      ? "bg-green-100 text-green-800"
      : score >= 60
      ? "bg-yellow-100 text-yellow-800"
      : "bg-red-100 text-red-800";

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}>
      {score}
    </span>
  );
}
