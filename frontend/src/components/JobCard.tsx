import type { JobPosting } from "../api/types";
import { ScoreBadge } from "./ScoreBadge";
import { StatusChip } from "./StatusChip";

interface Props {
  job: JobPosting;
  onClick: () => void;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function JobCard({ job, onClick }: Props) {
  return (
    <div
      className="border rounded-lg p-4 bg-white hover:shadow-md cursor-pointer transition-shadow"
      onClick={onClick}
      data-testid={`job-card-${job.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 truncate">{job.title}</h3>
          <p className="text-sm text-gray-500 mt-0.5">{job.company_id}</p>
        </div>
        <ScoreBadge job={job} />
      </div>
      <div className="flex items-center gap-2 mt-2">
        <StatusChip status={job.application_status} />
        {job.language !== "en" && (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700">
            {job.language}
          </span>
        )}
        <span className="text-xs text-gray-400 ml-auto">{formatDate(job.crawled_at)}</span>
      </div>
    </div>
  );
}
