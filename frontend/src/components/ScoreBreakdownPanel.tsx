import type { ScoreBreakdown } from "../api/types";

interface Props {
  breakdown: ScoreBreakdown;
}

const DIMENSION_LABELS: Record<string, string> = {
  role_fit: "Role Fit",
  stack_fit: "Stack Fit",
  seniority_fit: "Seniority Fit",
  location_fit: "Location Fit",
};

export function ScoreBreakdownPanel({ breakdown }: Props) {
  return (
    <div className="space-y-3" data-testid="score-breakdown">
      {breakdown.low_signal_jd && (
        <div className="text-xs bg-amber-50 text-amber-700 px-3 py-1.5 rounded border border-amber-200">
          Low signal JD — score capped at 70
        </div>
      )}
      <p className="text-sm text-gray-700">{breakdown.summary}</p>
      {Object.entries(breakdown.dimensions).map(([key, dim]) => (
        <div key={key} data-testid={`dimension-${key}`}>
          <div className="flex justify-between text-xs text-gray-600 mb-1">
            <span>{DIMENSION_LABELS[key] ?? key}</span>
            <span className="font-medium">{dim.score}</span>
          </div>
          <div className="h-1.5 bg-gray-200 rounded-full">
            <div
              className="h-1.5 bg-blue-500 rounded-full"
              style={{ width: `${dim.score}%` }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-1">{dim.reasoning}</p>
        </div>
      ))}
      {breakdown.flags.length > 0 && (
        <div data-testid="flags">
          <p className="text-xs font-medium text-red-600 mb-1">Flags</p>
          <ul className="list-disc list-inside text-xs text-red-600 space-y-0.5">
            {breakdown.flags.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
