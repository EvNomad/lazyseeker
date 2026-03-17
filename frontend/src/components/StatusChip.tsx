import type { JobPosting } from "../api/types";

const STATUS_COLORS: Record<JobPosting["application_status"], string> = {
  new: "bg-blue-100 text-blue-800",
  reviewing: "bg-purple-100 text-purple-800",
  applied: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  archived: "bg-gray-100 text-gray-600",
};

interface Props {
  status: JobPosting["application_status"];
}

export function StatusChip({ status }: Props) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[status]}`}
    >
      {status}
    </span>
  );
}
