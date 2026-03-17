import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getJobSuggestions, tailorJob, patchSuggestion, getTailoredCv, getJob, ApiError } from "../api/client";
import type { Suggestion } from "../api/types";
import { SuggestionCard } from "../components/SuggestionCard";

export default function SuggestionsView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [cvVersionCurrent, setCvVersionCurrent] = useState<string>("");
  const [jobTitle, setJobTitle] = useState<string>("Job");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    loadSuggestions();
    getJob(id).then((job) => setJobTitle(job.title)).catch(() => {});
  }, [id]);

  function loadSuggestions() {
    if (!id) return;
    setLoading(true);
    getJobSuggestions(id)
      .then(({ suggestions, cv_version_current }) => {
        setSuggestions(suggestions);
        setCvVersionCurrent(cv_version_current);
      })
      .catch((e) => setError(e instanceof ApiError ? `Error: ${e.status}` : "Failed to load"))
      .finally(() => setLoading(false));
  }

  async function handleGenerate() {
    if (!id) return;
    setGenerating(true);
    try {
      await tailorJob(id);
      loadSuggestions();
    } catch (e) {
      setError(e instanceof ApiError ? `Error: ${e.status}` : "Failed to generate");
    } finally {
      setGenerating(false);
    }
  }

  async function handleApprove(suggestionId: string) {
    const updated = await patchSuggestion(suggestionId, "approved");
    setSuggestions((prev) => prev.map((s) => (s.id === suggestionId ? updated : s)));
  }

  async function handleReject(suggestionId: string) {
    const updated = await patchSuggestion(suggestionId, "rejected");
    setSuggestions((prev) => prev.map((s) => (s.id === suggestionId ? updated : s)));
  }

  function triggerDownload(content: string, filename: string) {
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function buildFallbackMarkdown(): string {
    const approvedSuggestions = suggestions.filter((s) => s.status === "approved");
    const sections = approvedSuggestions
      .map(
        (s) =>
          `## ${s.section}\n**Original:** ${s.original}\n**Suggested:** ${s.suggested}\n> Rationale: ${s.rationale}`
      )
      .join("\n\n");
    return `# CV Suggestions for ${jobTitle}\n\n${sections}`;
  }

  async function handleExport() {
    if (!id) return;
    setExportError(null);
    try {
      const md = await getTailoredCv(id);
      triggerDownload(md, "tailored-cv.md");
    } catch (e) {
      const message = e instanceof ApiError ? `Export failed (${e.status}). Downloading raw suggestions instead.` : "Export failed. Downloading raw suggestions instead.";
      setExportError(message);
      triggerDownload(buildFallbackMarkdown(), "tailored-cv.md");
    }
  }

  const hasApproved = suggestions.some((s) => s.status === "approved");
  const hasCvMismatch = suggestions.some((s) => s.cv_version !== cvVersionCurrent);

  if (loading) return <div data-testid="loading">Loading...</div>;
  if (error) return <div data-testid="error">{error}</div>;

  return (
    <div data-testid="suggestions-view" className="max-w-3xl mx-auto space-y-4">
      <button onClick={() => navigate(-1)} className="text-sm text-blue-600 hover:underline">← Back</button>
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-gray-900">CV Suggestions</h1>
        <div className="flex gap-2">
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            data-testid="generate-btn"
          >
            {generating ? "Generating..." : "Regenerate"}
          </button>
          <button
            onClick={handleExport}
            disabled={!hasApproved}
            className="px-3 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
            data-testid="export-btn"
          >
            Export CV
          </button>
        </div>
      </div>
      {exportError && (
        <div className="text-xs bg-red-50 text-red-700 px-3 py-2 rounded border border-red-200" data-testid="export-error">
          {exportError}
        </div>
      )}
      {hasCvMismatch && (
        <div className="text-xs bg-yellow-50 text-yellow-700 px-3 py-2 rounded border border-yellow-200" data-testid="cv-mismatch-warning">
          Your CV has been updated since these suggestions were generated. Consider regenerating.
        </div>
      )}
      {suggestions.length === 0 ? (
        <p data-testid="empty-state">No suggestions yet. Click Regenerate to generate suggestions.</p>
      ) : (
        <div className="space-y-4" data-testid="suggestion-list">
          {suggestions.map((s) => (
            <SuggestionCard
              key={s.id}
              suggestion={s}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))}
        </div>
      )}
    </div>
  );
}
