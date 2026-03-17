import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getJob, ApiError } from "../api/client";
import type { JobPostingWithCompany, ScoreBreakdown } from "../api/types";
import { ScoreBadge } from "../components/ScoreBadge";
import { StatusChip } from "../components/StatusChip";
import { ScoreBreakdownPanel } from "../components/ScoreBreakdownPanel";

export default function JobDetailView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<JobPostingWithCompany | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getJob(id)
      .then(setJob)
      .catch((e) => setError(e instanceof ApiError ? `Error: ${e.status}` : "Failed to load job"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div data-testid="loading">Loading...</div>;
  if (error) return <div data-testid="error">{error}</div>;
  if (!job) return null;

  const breakdown: ScoreBreakdown | null = job.score_breakdown
    ? (() => { try { return JSON.parse(job.score_breakdown!); } catch { return null; } })()
    : null;

  return (
    <div data-testid="job-detail" className="max-w-2xl mx-auto space-y-6">
      <button onClick={() => navigate(-1)} className="text-sm text-blue-600 hover:underline">← Back</button>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{job.title}</h1>
          <p className="text-sm text-gray-500">{job.company?.name ?? job.company_id}</p>
        </div>
        <ScoreBadge job={job} />
      </div>
      <div className="flex items-center gap-3">
        <StatusChip status={job.application_status} />
        <a href={job.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:underline">
          View posting ↗
        </a>
        <button
          onClick={() => navigate(`/jobs/${id}/suggestions`)}
          className="ml-auto px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
          data-testid="tailor-btn"
        >
          Tailor CV
        </button>
      </div>
      {breakdown && <ScoreBreakdownPanel breakdown={breakdown} />}
      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-2">Description</h2>
        <p className="text-sm text-gray-600 whitespace-pre-wrap">{job.description}</p>
      </div>
    </div>
  );
}
