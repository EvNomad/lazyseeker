import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getJobs, ApiError } from "../api/client";
import type { JobPosting } from "../api/types";
import { JobCard } from "../components/JobCard";

export default function JobFeedView() {
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [languageFilter, setLanguageFilter] = useState<string>("");
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    setError(null);
    getJobs(languageFilter ? { language: languageFilter } : undefined)
      .then(setJobs)
      .catch((e) =>
        setError(e instanceof ApiError ? `API error: ${e.status}` : "Failed to load jobs")
      )
      .finally(() => setLoading(false));
  }, [languageFilter]);

  if (loading) return <div data-testid="loading">Loading...</div>;
  if (error) return <div data-testid="error">{error}</div>;

  return (
    <div data-testid="job-feed">
      <div className="flex items-center gap-3 mb-4">
        <select
          data-testid="language-filter"
          value={languageFilter}
          onChange={(e) => setLanguageFilter(e.target.value)}
          className="border rounded px-2 py-1 text-sm"
        >
          <option value="">All languages</option>
          <option value="en">English</option>
          <option value="he">Hebrew</option>
          <option value="mixed">Mixed</option>
        </select>
        <span className="text-sm text-gray-500">{jobs.length} jobs</span>
      </div>
      {jobs.length === 0 ? (
        <p data-testid="empty-state">No jobs found.</p>
      ) : (
        <div className="flex flex-col gap-3" data-testid="job-list">
          {jobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onClick={() => navigate(`/jobs/${job.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
