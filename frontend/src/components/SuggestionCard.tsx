import type { Suggestion } from "../api/types";

interface Props {
  suggestion: Suggestion;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

export function SuggestionCard({ suggestion, onApprove, onReject }: Props) {
  const isPending = suggestion.status === "pending";
  return (
    <div className="border rounded-lg p-4 bg-white" data-testid={`suggestion-${suggestion.id}`}>
      <p className="text-xs font-medium text-gray-500 uppercase mb-2">{suggestion.section}</p>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <p className="text-xs text-gray-400 mb-1">Original</p>
          <p className="text-sm text-gray-700 bg-red-50 rounded p-2" data-testid="original-text">{suggestion.original}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 mb-1">Suggested</p>
          <p className="text-sm text-gray-700 bg-green-50 rounded p-2" data-testid="suggested-text">{suggestion.suggested}</p>
        </div>
      </div>
      <p className="text-xs text-gray-500 italic mb-3" data-testid="rationale">{suggestion.rationale}</p>
      {isPending ? (
        <div className="flex gap-2">
          <button
            onClick={() => onApprove(suggestion.id)}
            className="px-3 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700"
            data-testid="approve-btn"
          >
            Approve
          </button>
          <button
            onClick={() => onReject(suggestion.id)}
            className="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
            data-testid="reject-btn"
          >
            Reject
          </button>
        </div>
      ) : (
        <span className={`text-xs font-medium ${suggestion.status === "approved" ? "text-green-600" : "text-red-600"}`}>
          {suggestion.status}
        </span>
      )}
    </div>
  );
}
