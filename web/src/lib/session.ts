const KEY = 'mpc-session-v1'

export type StoredMessage = {
  role: 'user' | 'assistant'
  text: string
  score?: number | null
  mode?: 'live' | 'demo'
}

export type ChatSession = {
  threads: Record<string, StoredMessage[]>
  drafts: Record<string, string>
  nCandidates: number
  useRerank: boolean
  ttsMuted: boolean
  lastCharacterId: string | null
}

const defaults: ChatSession = {
  threads: {},
  drafts: {},
  nCandidates: 3,
  useRerank: true,
  ttsMuted: true,
  lastCharacterId: null,
}

export function loadChatSession(): ChatSession {
  if (typeof window === 'undefined') return { ...defaults, threads: {}, drafts: {} }
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return { ...defaults, threads: {}, drafts: {} }
    const parsed = JSON.parse(raw) as Partial<ChatSession>
    return {
      threads: parsed.threads ?? {},
      drafts: parsed.drafts ?? {},
      nCandidates:
        typeof parsed.nCandidates === 'number' ? parsed.nCandidates : 3,
      useRerank: parsed.useRerank ?? true,
      ttsMuted: parsed.ttsMuted ?? true,
      lastCharacterId: parsed.lastCharacterId ?? null,
    }
  } catch {
    return { ...defaults, threads: {}, drafts: {} }
  }
}

export function saveChatSession(session: ChatSession): void {
  if (typeof window === 'undefined') return
  try {
    sessionStorage.setItem(KEY, JSON.stringify(session))
  } catch {
    /* quota / private mode */
  }
}
