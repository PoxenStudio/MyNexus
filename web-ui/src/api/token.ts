import { apiClient } from "./client";

export interface TokenCallsiteBreakdown {
  call_site: string;
  llm_provider: string;
  llm_model: string;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface BookTokenUsage {
  book_id: string;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  calls: number;
  breakdown: TokenCallsiteBreakdown[];
}

export interface DailyProviderRow {
  date: string;
  llm_provider: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface TokenStats {
  range_days: number;
  daily: DailyProviderRow[];
  today_by_provider: Record<string, number>;
}

export function fetchBookTokenUsage(bookId: string): Promise<BookTokenUsage> {
  return apiClient.get(`/books/${bookId}/token-usage`).then((r) => r.data);
}

export function fetchTokenStats(range: number = 7): Promise<TokenStats> {
  return apiClient.get(`/system/token-stats`, { params: { range } }).then((r) => r.data);
}

// Formats raw token counts into compact human-readable strings — 1234 →
// "1.2K" rather than just dumping the number, since a big book can easily
// clock in at five figures. Stays at three significant figures so it never
// takes up more than ~6 chars on a pill/stat card regardless of magnitude.
export function formatTokens(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return "0";
  if (n < 1000) return String(n);
  if (n < 1_000_000) return (n / 1000).toFixed(n < 10_000 ? 1 : 0) + "K";
  return (n / 1_000_000).toFixed(1) + "M";
}
