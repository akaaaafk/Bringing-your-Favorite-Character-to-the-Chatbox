import { isRemoteApi } from './apiBase'

const KEY = 'mpc-session-v1'
/** One-time: public deploys switch to fast defaults without wiping chat threads. */
const PUBLIC_FAST_KEY = 'mpc-public-fast-v1'
/** One-time: turn spoken replies on by default for existing sessions. */
const UNMUTE_KEY = 'mpc-unmute-v1'

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

/** Local keeps Best-of-N; public (VITE_API_BASE set) defaults to single-sample. */
export function defaultNCandidates(): number {
  return isRemoteApi() ? 1 : 3
}

export function defaultUseRerank(): boolean {
  return !isRemoteApi()
}

function buildDefaults(): ChatSession {
  return {
    threads: {},
    drafts: {},
    nCandidates: defaultNCandidates(),
    useRerank: defaultUseRerank(),
    ttsMuted: false,
    lastCharacterId: null,
  }
}

export function loadChatSession(): ChatSession {
  const defaults = buildDefaults()
  if (typeof window === 'undefined') {
    return { ...defaults, threads: {}, drafts: {} }
  }
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return { ...defaults, threads: {}, drafts: {} }
    const parsed = JSON.parse(raw) as Partial<ChatSession>

    let nCandidates =
      typeof parsed.nCandidates === 'number'
        ? parsed.nCandidates
        : defaults.nCandidates
    let useRerank =
      typeof parsed.useRerank === 'boolean'
        ? parsed.useRerank
        : defaults.useRerank
    let ttsMuted =
      typeof parsed.ttsMuted === 'boolean' ? parsed.ttsMuted : defaults.ttsMuted

    // Existing public sessions may still have n=3 + rerank from before; flip once.
    if (isRemoteApi() && !sessionStorage.getItem(PUBLIC_FAST_KEY)) {
      nCandidates = 1
      useRerank = false
      sessionStorage.setItem(PUBLIC_FAST_KEY, '1')
    }

    // Existing sessions defaulted to muted; unmute once.
    if (!sessionStorage.getItem(UNMUTE_KEY)) {
      ttsMuted = false
      sessionStorage.setItem(UNMUTE_KEY, '1')
    }

    return {
      threads: parsed.threads ?? {},
      drafts: parsed.drafts ?? {},
      nCandidates,
      useRerank,
      ttsMuted,
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
