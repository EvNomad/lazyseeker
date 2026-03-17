export interface JobPosting {
  id: string;
  url: string;
  url_hash: string;
  company_id: string;
  title: string;
  description: string;
  requirements: string | null;
  language: "en" | "he" | "mixed";
  source: "career_page" | "linkedin";
  crawled_at: string;
  overall_score: number | null;
  score_breakdown: string | null;
  score_status: "pending" | "scored" | "error";
  application_status: "new" | "reviewing" | "applied" | "rejected" | "archived";
  repost_of: string | null;
}

export interface Company {
  id: string;
  name: string;
  career_page_url: string;
  linkedin_slug: string | null;
  active: boolean;
  last_crawled_at: string | null;
}

export interface JobPostingWithCompany extends JobPosting {
  company: Company | null;
}

export interface DimensionScore {
  score: number;
  reasoning: string;
}

export interface ScoreBreakdown {
  overall_score: number;
  low_signal_jd: boolean;
  dimensions: {
    role_fit: DimensionScore;
    stack_fit: DimensionScore;
    seniority_fit: DimensionScore;
    location_fit: DimensionScore;
  };
  flags: string[];
  summary: string;
}

export interface UserProfile {
  id: string;
  cv_markdown: string;
  preferences: string;
  updated_at: string;
}

export interface Suggestion {
  id: string;
  job_id: string;
  section: string;
  original: string;
  suggested: string;
  rationale: string;
  status: "pending" | "approved" | "rejected";
  cv_version: string;
  created_at: string;
}

export interface CrawlLogEntry {
  company_id: string;
  company_name: string;
  run_at: string;
  status: "success" | "error";
  new_postings: number;
  error_message: string | null;
}
