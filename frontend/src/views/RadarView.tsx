import { useState, useEffect } from "react";
import { triggerCrawl, getCrawlLog, ApiError } from "../api/client";
import type { CrawlLogEntry } from "../api/types";

export default function RadarView() {
  const [log, setLog] = useState<CrawlLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [crawlInProgress, setCrawlInProgress] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchLog = () => {
      getCrawlLog()
        .then((data) => {
          if (!cancelled) {
            setLog(data);
            setLoading(false);
          }
        })
        .catch((e) => {
          if (!cancelled) {
            setError(e instanceof ApiError ? `API error: ${e.status}` : "Failed to load crawl log");
            setLoading(false);
          }
        });
    };

    fetchLog();
    const interval = setInterval(fetchLog, 10000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const handleRunCrawl = () => {
    setRunError(null);
    setCrawlInProgress(false);
    triggerCrawl()
      .then(() => {
        // success — next poll will refresh the log
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 409) {
          setCrawlInProgress(true);
        } else {
          setRunError(e instanceof ApiError ? `Failed to start crawl: ${e.status}` : "Failed to start crawl");
        }
      });
  };

  if (loading) return <div data-testid="loading">Loading...</div>;
  if (error) return <div data-testid="error">{error}</div>;

  return (
    <div data-testid="radar-view" className="p-4">
      <div className="flex items-center gap-4 mb-4">
        <h1 className="text-xl font-semibold">Radar</h1>
        <button
          data-testid="run-btn"
          onClick={handleRunCrawl}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >
          Run Crawl
        </button>
      </div>

      {crawlInProgress && (
        <p className="text-yellow-600 mb-4">Crawl in progress...</p>
      )}
      {runError && (
        <p className="text-red-600 mb-4">{runError}</p>
      )}

      {log.length === 0 ? (
        <p className="text-gray-500">No crawl runs recorded yet.</p>
      ) : (
        <table data-testid="crawl-log" className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b bg-gray-50">
              <th className="text-left p-2">Company</th>
              <th className="text-left p-2">Status</th>
              <th className="text-left p-2">New Postings</th>
              <th className="text-left p-2">Run At</th>
              <th className="text-left p-2">Error Message</th>
            </tr>
          </thead>
          <tbody>
            {log.map((entry) => (
              <tr key={`${entry.company_id}-${entry.run_at}`} className="border-b">
                <td className="p-2">{entry.company_name}</td>
                <td className="p-2">{entry.status}</td>
                <td className="p-2">{entry.new_postings}</td>
                <td className="p-2">{new Date(entry.run_at).toLocaleString()}</td>
                <td className="p-2">{entry.error_message ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
