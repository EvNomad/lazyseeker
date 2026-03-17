import { useState, useEffect } from "react";
import { getProfile, putProfile, ApiError } from "../api/client";
import type { UserProfile } from "../api/types";

interface ProfileFormData {
  name: string;
  email: string;
  cv_markdown: string;
  preferences: string;
}

export default function ProfileView() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [form, setForm] = useState<ProfileFormData>({
    name: "",
    email: "",
    cv_markdown: "",
    preferences: "",
  });

  useEffect(() => {
    getProfile()
      .then((profile: UserProfile) => {
        setForm({
          name: profile.name ?? "",
          email: profile.email ?? "",
          cv_markdown: profile.cv_markdown ?? "",
          preferences: profile.preferences ?? "",
        });
        setLoading(false);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) {
          // No profile yet — start with empty form
          setLoading(false);
        } else {
          setError(e instanceof ApiError ? `API error: ${e.status}` : "Failed to load profile");
          setLoading(false);
        }
      });
  }, []);

  const handleChange = (field: keyof ProfileFormData) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSaveSuccess(false);
    setSaveError(null);
    putProfile({
      cv_markdown: form.cv_markdown,
      preferences: form.preferences,
    })
      .then(() => {
        setSaveSuccess(true);
      })
      .catch((err) => {
        setSaveError(err instanceof ApiError ? `Save failed: ${err.status}` : "Save failed");
      });
  };

  if (loading) return <div data-testid="loading">Loading...</div>;
  if (error) return <div data-testid="error">{error}</div>;

  return (
    <div data-testid="profile-view" className="p-4 max-w-2xl">
      <h1 className="text-xl font-semibold mb-4">Profile</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <label className="block text-sm font-medium mb-1" htmlFor="name">
            Name
          </label>
          <input
            id="name"
            data-testid="name-input"
            type="text"
            value={form.name}
            onChange={handleChange("name")}
            className="border rounded px-3 py-2 w-full"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            data-testid="email-input"
            type="email"
            value={form.email}
            onChange={handleChange("email")}
            className="border rounded px-3 py-2 w-full"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1" htmlFor="preferences">
            Preferences
          </label>
          <input
            id="preferences"
            data-testid="preferences-input"
            type="text"
            value={form.preferences}
            onChange={handleChange("preferences")}
            className="border rounded px-3 py-2 w-full"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1" htmlFor="cv_markdown">
            CV (Markdown)
          </label>
          <textarea
            id="cv_markdown"
            data-testid="cv-textarea"
            value={form.cv_markdown}
            onChange={handleChange("cv_markdown")}
            rows={12}
            className="border rounded px-3 py-2 w-full font-mono text-sm"
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            type="submit"
            data-testid="save-btn"
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            Save
          </button>
          {saveSuccess && (
            <span data-testid="save-success" className="text-green-600 text-sm">
              Profile saved successfully.
            </span>
          )}
          {saveError && (
            <span className="text-red-600 text-sm">{saveError}</span>
          )}
        </div>
      </form>
    </div>
  );
}
