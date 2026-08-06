const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export interface ChatSession {
  id: string;
  title: string;
  book_ids: string[];
  created_at: string;
  updated_at: string;
}

// Citation mirrors the shape Worker's QAPipeline emits per retrieved chunk
// (core-api/internal/api/dto/chat_dto.go CitationResponse) — book_id/chapter_id
// are raw ids, not titles; resolve those via the books API for display.
export interface Citation {
  chunk_id: string;
  chapter_id: string;
  book_id: string;
  score: number;
  content: string;
}

export interface ChatMessage {
  id: string;
  role: string;
  content: string;
  citations: Citation[];
  created_at: string;
}

export async function listSessions(): Promise<ChatSession[]> {
  const res = await fetch(`${API_BASE}/chat/sessions`, { credentials: "include" });
  if (!res.ok) throw new Error(`list sessions failed: ${res.status}`);
  const data = await res.json();
  return data.items;
}

export async function getSession(id: string): Promise<{ messages: ChatMessage[] } & ChatSession> {
  const res = await fetch(`${API_BASE}/chat/sessions/${id}`, { credentials: "include" });
  if (!res.ok) throw new Error(`get session failed: ${res.status}`);
  return res.json();
}

export async function deleteSession(id: string): Promise<void> {
  await fetch(`${API_BASE}/chat/sessions/${id}`, { method: "DELETE", credentials: "include" });
}

export async function renameSession(id: string, title: string): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/sessions/${id}`, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error(`rename session failed: ${res.status}`);
}

// streamCompletion posts the message history and reads the SSE response as it
// arrives, invoking onDelta for each answer fragment. Uses raw fetch (not
// axios) since axios doesn't expose a streamed-chunk callback in the browser.
export async function streamCompletion(
  sessionId: string | null,
  messages: { role: string; content: string }[],
  bookIds: string[],
  onDelta: (text: string) => void,
  onCitations?: (citations: Citation[]) => void,
): Promise<{ sessionId: string }> {
  const res = await fetch(`${API_BASE}/chat/completions`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId || "", messages, book_ids: bookIds }),
  });
  if (!res.ok || !res.body) {
    throw new Error(`chat completion failed: ${res.status}`);
  }
  const returnedSessionId = res.headers.get("X-Session-Id") || sessionId || "";

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const data = line.startsWith("data: ") ? line.slice(6) : null;
      if (!data || data === "[DONE]") continue;
      try {
        const event = JSON.parse(data);
        const delta = event?.choices?.[0]?.delta?.content;
        if (delta) onDelta(delta);
        if (event?.citations) onCitations?.(event.citations);
      } catch {
        // ignore malformed/partial SSE frames
      }
    }
  }

  return { sessionId: returnedSessionId };
}
