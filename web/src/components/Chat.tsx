import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from 'react'
import {
  ArrowLeft,
  ChevronDown,
  Mic,
  Send,
  Sparkles,
  Trash2,
  Volume2,
  VolumeX,
} from 'lucide-react'
import { sendChat } from '../api/chat'
import { CHARACTERS, type Character } from '../data/characters'
import {
  cancelSpeech,
  createToggleListener,
  getSpeechSupport,
  speakText,
} from '../lib/speech'
import { loadChatSession, saveChatSession } from '../lib/session'
import ClickSpark from './react-bits/ClickSpark'
import { CharacterAvatar, type AvatarMood } from './CharacterAvatar'

interface Message {
  role: 'user' | 'assistant'
  text: string
  score?: number | null
  mode?: 'live' | 'demo'
}

interface ChatProps {
  initialCharacter?: Character
  onBack: () => void
}

function resolveInitialCharacter(initial?: Character): Character {
  if (initial) return initial
  const savedId = loadChatSession().lastCharacterId
  return CHARACTERS.find((c) => c.id === savedId) ?? CHARACTERS[0]
}

export function Chat({ initialCharacter, onBack }: ChatProps) {
  const session = loadChatSession()
  const [character, setCharacter] = useState<Character>(() =>
    resolveInitialCharacter(initialCharacter),
  )
  const [threads, setThreads] = useState<Record<string, Message[]>>(
    () => session.threads,
  )
  const [drafts, setDrafts] = useState<Record<string, string>>(
    () => session.drafts,
  )
  const [input, setInput] = useState(() => {
    const c = resolveInitialCharacter(initialCharacter)
    const saved = session.drafts[c.id]
    const thread = session.threads[c.id] ?? []
    if (saved !== undefined) return saved
    return thread.length === 0 ? c.example : ''
  })
  const [nCandidates, setNCandidates] = useState(session.nCandidates)
  const [useRerank, setUseRerank] = useState(session.useRerank)
  const [loading, setLoading] = useState(false)
  const [demoBanner, setDemoBanner] = useState(false)
  const [recording, setRecording] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [ttsMuted, setTtsMuted] = useState(session.ttsMuted)
  const [voiceError, setVoiceError] = useState<string | null>(null)
  const [chatError, setChatError] = useState<string | null>(null)
  const [speechOk] = useState(() => getSpeechSupport())
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const mobileCastRef = useRef<HTMLDivElement>(null)
  const loadingRef = useRef(false)
  const characterIdRef = useRef(character.id)
  const listenerRef = useRef<ReturnType<typeof createToggleListener> | null>(
    null,
  )
  const pendingDraftRef = useRef('')
  const hydratedRef = useRef(false)

  const messages = threads[character.id] ?? []

  const avatarMood: AvatarMood = recording
    ? 'listening'
    : speaking
      ? 'speaking'
      : 'idle'

  useEffect(() => {
    characterIdRef.current = character.id
  }, [character.id])

  useEffect(() => {
    document.title = `${character.shortName} · Movie Persona Chat`
    return () => {
      document.title = 'Movie Persona Chat'
    }
  }, [character.shortName])

  useEffect(() => {
    if (!hydratedRef.current) {
      hydratedRef.current = true
      return
    }
    saveChatSession({
      threads,
      drafts,
      nCandidates,
      useRerank,
      ttsMuted,
      lastCharacterId: character.id,
    })
  }, [threads, drafts, nCandidates, useRerank, ttsMuted, character.id])

  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    bottomRef.current?.scrollIntoView({
      behavior: reduce ? 'auto' : 'smooth',
    })
  }, [messages, loading, recording])

  useEffect(() => {
    const root = mobileCastRef.current
    if (!root) return
    const active = root.querySelector<HTMLElement>('[aria-current="true"]')
    active?.scrollIntoView({
      behavior: 'smooth',
      inline: 'center',
      block: 'nearest',
    })
  }, [character.id])

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (recording) {
        e.preventDefault()
        listenerRef.current?.stop()
        return
      }
      if (speaking) {
        e.preventDefault()
        cancelSpeech()
        setSpeaking(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [recording, speaking])

  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 144)}px`
  }, [input])

  useEffect(() => {
    setVoiceError(null)
    setChatError(null)
    setRecording(false)
    setSpeaking(false)
    cancelSpeech()
    listenerRef.current?.abort()
    const saved = drafts[character.id]
    const thread = threads[character.id] ?? []
    setInput(
      saved !== undefined
        ? saved
        : thread.length === 0
          ? character.example
          : '',
    )
    // Only react to character switches; drafts/threads read from latest render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [character.id])

  useEffect(() => {
    loadingRef.current = loading
  }, [loading])

  useEffect(() => {
    let cancelled = false
    fetch('/api/health')
      .then(async (res) => {
        if (cancelled) return
        if (!res.ok) {
          setDemoBanner(true)
          return
        }
        const body = (await res.json()) as {
          pipeline_loaded?: boolean
        }
        if (!body.pipeline_loaded) setDemoBanner(true)
      })
      .catch(() => {
        if (!cancelled) setDemoBanner(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const updateThread = useCallback(
    (characterId: string, updater: (prev: Message[]) => Message[]) => {
      setThreads((prev) => ({
        ...prev,
        [characterId]: updater(prev[characterId] ?? []),
      }))
    },
    [],
  )

  const sendMessage = useCallback(
    async (raw: string) => {
      const text = raw.trim()
      if (!text || loadingRef.current) return

      const activeId = characterIdRef.current
      pendingDraftRef.current = text
      setInput('')
      setDrafts((d) => ({ ...d, [activeId]: '' }))
      setVoiceError(null)
      setChatError(null)
      updateThread(activeId, (m) => [...m, { role: 'user', text }])
      setLoading(true)
      cancelSpeech()
      setSpeaking(false)

      try {
        const res = await sendChat({
          message: text,
          character: activeId,
          n_candidates: nCandidates,
          use_rerank: useRerank,
        })
        if (res.mode === 'demo') setDemoBanner(true)
        pendingDraftRef.current = ''
        updateThread(activeId, (m) => [
          ...m,
          {
            role: 'assistant',
            text: res.reply,
            score: res.persona_score,
            mode: res.mode,
          },
        ])

        if (
          speechOk.synthesis &&
          !ttsMuted &&
          res.reply.trim() &&
          characterIdRef.current === activeId
        ) {
          speakText(res.reply, {
            onStart: () => setSpeaking(true),
            onEnd: () => setSpeaking(false),
          })
        }
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Chat request failed.'
        setChatError(
          /HTTP|fetch|network|Failed|Server|API/i.test(message)
            ? `${message} Your line is still in the box — tap Retry when ready.`
            : message,
        )
        setInput(pendingDraftRef.current)
        setDrafts((d) => ({
          ...d,
          [activeId]: pendingDraftRef.current,
        }))
        updateThread(activeId, (m) =>
          m.length && m[m.length - 1]?.role === 'user' ? m.slice(0, -1) : m,
        )
      } finally {
        setLoading(false)
        if (characterIdRef.current === activeId) {
          inputRef.current?.focus()
        }
      }
    },
    [nCandidates, useRerank, speechOk.synthesis, ttsMuted, updateThread],
  )

  useEffect(() => {
    listenerRef.current = createToggleListener({
      onStart: () => {
        setRecording(true)
        setVoiceError(null)
      },
      onInterim: (text) => setInput(text),
      onFinal: (text) => {
        setRecording(false)
        if (text.trim()) void sendMessage(text)
        else setVoiceError('No speech detected. Tap the mic and try again.')
      },
      onError: (message) => {
        setRecording(false)
        setVoiceError(message)
      },
      onEnd: () => setRecording(false),
    })

    return () => {
      listenerRef.current?.abort()
      cancelSpeech()
    }
  }, [sendMessage])

  function handleSend() {
    void sendMessage(input)
  }

  function toggleMic() {
    if (!speechOk.recognition) {
      setVoiceError(
        'Voice input is not supported here. Open in Google Chrome, or type instead.',
      )
      return
    }
    if (loading) return

    const listener = listenerRef.current
    if (!listener?.supported) return

    if (recording) {
      listener.stop()
      return
    }

    cancelSpeech()
    setSpeaking(false)
    setInput('')
    listener.start()
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function selectCharacter(next: Character) {
    if (next.id === character.id) return
    setDrafts((d) => ({ ...d, [character.id]: input }))
    cancelSpeech()
    setSpeaking(false)
    listenerRef.current?.abort()
    setRecording(false)
    setCharacter(next)
  }

  function stopSpeaking() {
    cancelSpeech()
    setSpeaking(false)
  }

  function toggleTtsMuted() {
    setTtsMuted((muted) => {
      if (!muted) {
        cancelSpeech()
        setSpeaking(false)
      }
      return !muted
    })
  }

  function clearChat() {
    if (
      messages.length > 0 &&
      !window.confirm(`Clear your chat with ${character.shortName}?`)
    ) {
      return
    }
    cancelSpeech()
    setSpeaking(false)
    listenerRef.current?.abort()
    setRecording(false)
    setThreads((prev) => ({ ...prev, [character.id]: [] }))
    setInput(character.example)
    setDrafts((d) => ({ ...d, [character.id]: character.example }))
    setVoiceError(null)
    setChatError(null)
  }

  function retryLastDraft() {
    const draft = input.trim() || pendingDraftRef.current
    if (draft) void sendMessage(draft)
  }

  function onInputChange(value: string) {
    const next = value.slice(0, 2000)
    setInput(next)
    setDrafts((d) => ({ ...d, [character.id]: next }))
  }

  const stageSummary = useRerank
    ? `Takes · ${nCandidates}`
    : 'Takes · off'

  const stageControls = (
    <div className="space-y-1">
      <div>
        <p className="font-serif text-lg tracking-[-0.02em] text-foreground">
          Takes
        </p>
        <p className="mt-1 text-xs leading-relaxed text-muted-fg">
          Write a few options and keep the one that sounds most like them.
        </p>
      </div>

      <button
        type="button"
        role="switch"
        aria-checked={useRerank}
        onClick={() => setUseRerank((v) => !v)}
        className="stage-switch-row mt-4"
      >
        <span className="text-sm text-foreground">Sharper replies</span>
        <span className="stage-switch" aria-hidden />
      </button>

      <div
        className={`stage-takes ${useRerank ? 'is-open' : ''}`}
        aria-hidden={!useRerank}
      >
        <div>
          <div className="flex items-baseline justify-between gap-3 pt-4">
            <span className="text-sm text-muted-fg">Options</span>
            <span className="font-serif text-xl tabular-nums tracking-tight text-accent">
              {nCandidates}
            </span>
          </div>
          <label className="mt-2 block">
            <span className="sr-only">Number of reply options</span>
            <input
              type="range"
              min={1}
              max={8}
              value={nCandidates}
              disabled={!useRerank}
              tabIndex={useRerank ? 0 : -1}
              onChange={(e) => setNCandidates(Number(e.target.value))}
              className="stage-range"
            />
          </label>
          <div className="mt-1.5 flex justify-between text-[0.65rem] tracking-wide text-muted-fg">
            <span>Faster</span>
            <span>Richer</span>
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={clearChat}
        className="mt-4 inline-flex min-h-10 w-full cursor-pointer items-center justify-center gap-2 rounded-lg px-2 py-2 text-xs tracking-wide text-muted-fg transition duration-200 hover:bg-muted/60 hover:text-destructive focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      >
        <Trash2 className="h-3.5 w-3.5" aria-hidden />
        Clear chat
      </button>
    </div>
  )

  const desktopCastList = CHARACTERS.map((c) => {
    const active = c.id === character.id
    const hasChat = (threads[c.id]?.length ?? 0) > 0
    return (
      <button
        key={c.id}
        type="button"
        onClick={() => selectCharacter(c)}
        aria-current={active ? 'true' : undefined}
        className={`cast-rail flex min-w-0 cursor-pointer items-center gap-3 rounded-xl border px-2.5 py-2.5 text-left active:scale-[0.98] ${
          active
            ? 'border-accent/45 bg-muted'
            : 'border-transparent bg-transparent hover:border-white/10 hover:bg-muted/50'
        }`}
        style={
          active
            ? ({
                '--rail-accent': c.accent,
                boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${c.accent} 35%, transparent)`,
              } as CSSProperties)
            : undefined
        }
      >
        <span className="relative shrink-0">
          <CharacterAvatar
            character={c}
            size="sm"
            mood={active ? avatarMood : 'idle'}
          />
          {hasChat && !active && (
            <span
              className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-accent shadow-[0_0_0_2px_var(--color-card)]"
              aria-hidden
            />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-foreground">
            {c.shortName}
          </span>
          <span className="mt-0.5 block text-xs text-muted-fg line-clamp-2">
            {c.film}
          </span>
        </span>
      </button>
    )
  })

  const mobileCastChips = CHARACTERS.map((c) => {
    const active = c.id === character.id
    const hasChat = (threads[c.id]?.length ?? 0) > 0
    return (
      <button
        key={c.id}
        type="button"
        onClick={() => selectCharacter(c)}
        aria-current={active ? 'true' : undefined}
        aria-label={hasChat ? `${c.shortName}, conversation started` : c.shortName}
        className={`relative inline-flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full border transition duration-200 active:scale-[0.96] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
          active
            ? 'border-accent/60 bg-muted'
            : 'border-white/10 bg-transparent opacity-75 hover:opacity-100'
        }`}
        style={
          active
            ? {
                boxShadow: `0 0 0 2px color-mix(in oklab, ${c.accent} 45%, transparent)`,
              }
            : undefined
        }
      >
        <CharacterAvatar
          character={c}
          size="sm"
          mood={active ? avatarMood : 'idle'}
          className="!h-9 !w-9"
        />
        {hasChat && !active && (
          <span
            className="absolute right-0 top-0 h-2 w-2 rounded-full bg-accent shadow-[0_0_0_2px_var(--color-background)]"
            aria-hidden
          />
        )}
      </button>
    )
  })

  return (
    <div className="view-fade flex h-dvh flex-col overflow-hidden bg-background lg:flex-row">
      <aside className="hidden w-[19rem] shrink-0 flex-col border-r border-white/8 bg-card/55 lg:flex xl:w-80">
        <div className="flex items-center gap-3 border-b border-white/8 px-4 py-3.5">
          <button
            type="button"
            onClick={onBack}
            className="inline-flex min-h-10 cursor-pointer items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-muted-fg transition duration-200 hover:bg-muted hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden />
            Cast
          </button>
          <span className="font-serif text-lg tracking-[-0.01em] text-foreground">
            Chat
          </span>
        </div>

        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-3 py-3">
          {desktopCastList}
        </div>

        <div className="mt-auto border-t border-white/8 px-4 py-4">
          {stageControls}
        </div>
      </aside>

      <main className="relative flex min-h-0 min-w-0 flex-1 flex-col">
        <div
          key={character.id}
          className="glow-crossfade pointer-events-none absolute inset-0 opacity-55"
          style={{
            background: `radial-gradient(ellipse 55% 38% at 82% 0%, ${character.glow}, transparent 62%)`,
          }}
          aria-hidden
        />

        <header className="relative z-10 flex items-center justify-between gap-3 border-b border-white/8 bg-background/40 px-4 py-3 sm:px-8 sm:py-3.5">
          <div className="flex min-w-0 items-center gap-2.5 sm:gap-3.5">
            <button
              type="button"
              onClick={onBack}
              className="inline-flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-lg text-muted-fg transition hover:bg-muted hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring lg:hidden"
              aria-label="Back to cast"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden />
            </button>
            <div key={character.id} className="header-swap flex min-w-0 items-center gap-3">
              <CharacterAvatar
                character={character}
                size="md"
                mood={avatarMood}
                labelled
                className="!h-11 !w-11 sm:!h-14 sm:!w-14"
              />
              <div className="min-w-0">
                <h1 className="truncate font-serif text-lg tracking-[-0.02em] text-foreground sm:text-2xl">
                  {character.name}
                </h1>
                <p className="mt-0.5 flex items-center gap-2 truncate text-xs text-muted-fg sm:text-sm">
                  <span className="truncate">{character.film}</span>
                  {recording && (
                    <span className="mic-bars shrink-0 text-accent" aria-hidden>
                      <span />
                      <span />
                      <span />
                      <span />
                    </span>
                  )}
                  {!recording && speaking && (
                    <span
                      className="shrink-0 text-xs"
                      style={{ color: character.accent }}
                    >
                      Speaking
                    </span>
                  )}
                </p>
              </div>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
            {speechOk.synthesis && (
              <>
                {speaking && (
                  <button
                    type="button"
                    onClick={stopSpeaking}
                    className="inline-flex h-10 cursor-pointer items-center gap-1.5 rounded-lg border border-white/10 px-2.5 text-xs text-muted-fg transition hover:border-accent/40 hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  >
                    Stop
                  </button>
                )}
                <button
                  type="button"
                  onClick={toggleTtsMuted}
                  aria-pressed={ttsMuted}
                  aria-label={
                    ttsMuted ? 'Unmute spoken replies' : 'Mute spoken replies'
                  }
                  title={
                    ttsMuted ? 'Replies are silent' : 'Replies may speak aloud'
                  }
                  className={`inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-lg border transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
                    ttsMuted
                      ? 'border-white/10 text-muted-fg hover:border-accent/40 hover:text-accent'
                      : 'border-accent/45 bg-accent/10 text-accent'
                  }`}
                >
                  {ttsMuted ? (
                    <VolumeX className="h-4 w-4" aria-hidden />
                  ) : (
                    <Volume2 className="h-4 w-4" aria-hidden />
                  )}
                </button>
              </>
            )}
            {demoBanner && (
              <span className="hidden items-center gap-1.5 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs text-accent sm:inline-flex">
                <Sparkles className="h-3.5 w-3.5" aria-hidden />
                Preview
              </span>
            )}
          </div>
        </header>

        <div
          ref={mobileCastRef}
          className="relative z-10 flex items-center gap-2 overflow-x-auto border-b border-white/8 px-4 py-2.5 lg:hidden"
        >
          {mobileCastChips}
        </div>

        <details className="stage-drawer relative z-10 border-b border-white/8 lg:hidden">
          <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 px-4 py-2.5 text-sm text-muted-fg transition hover:bg-muted/40 hover:text-foreground">
            <span className="truncate">{stageSummary}</span>
            <ChevronDown
              className="stage-drawer-chevron h-4 w-4 shrink-0"
              aria-hidden
            />
          </summary>
          <div className="border-t border-white/8 px-4 py-4">{stageControls}</div>
        </details>

        <div className="thread-fade thread-scroll relative z-10 flex-1 space-y-4 overflow-y-auto px-4 py-4 sm:px-8 sm:py-6">
          <div className="sr-only" aria-live="polite" aria-atomic="true">
            {loading
              ? `${character.shortName} is writing`
              : recording
                ? 'Listening'
                : speaking
                  ? `${character.shortName} is speaking`
                  : ''}
          </div>
          {messages.length === 0 && !loading && (
            <div
              key={character.id}
              className="header-swap mx-auto flex w-full max-w-lg flex-col items-center px-1 py-8 text-center sm:py-14"
            >
              <div className="relative">
                <div
                  className="pointer-events-none absolute -inset-8 rounded-full opacity-70 blur-2xl"
                  style={{ background: character.glow }}
                  aria-hidden
                />
                <CharacterAvatar
                  character={character}
                  size="lg"
                  mood={avatarMood}
                  labelled
                />
              </div>
              <p className="mt-6 font-serif text-2xl tracking-[-0.02em] text-foreground">
                The scene is set.
              </p>
              <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-fg">
                Open with a line — or take {character.shortName}&apos;s cue.
              </p>
              <button
                type="button"
                onClick={() => void sendMessage(character.example)}
                className="cue-card group mt-7 w-full cursor-pointer rounded-2xl border border-white/10 bg-card/80 px-5 py-4 text-left hover:border-accent/40 hover:bg-card focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring active:scale-[0.99]"
              >
                <span
                  className="text-[10px] font-semibold uppercase tracking-[0.16em]"
                  style={{ color: character.accent }}
                >
                  Opening line
                </span>
                <span className="mt-2 block font-serif text-[1.05rem] leading-snug italic text-foreground/90">
                  “{character.example}”
                </span>
                <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-accent">
                  Send this cue
                  <Send
                    className="h-3 w-3 transition-transform group-hover:translate-x-0.5"
                    aria-hidden
                  />
                </span>
              </button>
              <p className="mt-4 text-xs text-muted-fg">
                Or tap the mic — tap again to send. Voice replies stay muted until you unmute.
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={`${msg.role}-${i}-${msg.text.slice(0, 24)}`}
              className={`flex items-end gap-2.5 ${
                msg.role === 'user'
                  ? 'msg-in-user justify-end'
                  : 'msg-in-assistant justify-start'
              }`}
            >
              {msg.role === 'assistant' && (
                <CharacterAvatar
                  character={character}
                  size="sm"
                  mood={
                    speaking && i === messages.length - 1 ? 'speaking' : 'idle'
                  }
                />
              )}
              <div
                className={`max-w-[min(100%,34rem)] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-secondary text-foreground shadow-[0_10px_24px_-14px_oklch(0.2_0.03_40_/_0.9)]'
                    : 'border border-white/10 bg-card/95 text-foreground'
                }`}
              >
                {msg.role === 'assistant' && (
                  <p
                    className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em]"
                    style={{ color: character.accent }}
                  >
                    {character.shortName}
                  </p>
                )}
                <p className="whitespace-pre-wrap break-words">{msg.text}</p>
              </div>
            </div>
          ))}

          {loading && (
            <div className="msg-in-assistant flex items-end justify-start gap-2.5">
              <CharacterAvatar
                character={character}
                size="sm"
                mood="listening"
              />
              <div
                className="inline-flex items-center gap-3 rounded-2xl border border-white/10 bg-card px-4 py-3 text-sm text-muted-fg"
                style={{
                  boxShadow: `0 12px 32px -20px ${character.glow}`,
                }}
              >
                <span
                  className="wait-dots"
                  style={{ color: character.accent }}
                  aria-hidden
                >
                  <span />
                  <span />
                  <span />
                </span>
                <span>{character.shortName} is finding the right voice…</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="relative z-10 border-t border-white/8 bg-background/90 px-4 py-3 safe-composer-pad sm:px-8">
          {chatError && (
            <div
              className="mx-auto mb-2 flex max-w-3xl flex-wrap items-center justify-between gap-2 text-xs text-destructive"
              role="alert"
            >
              <p className="min-w-0 flex-1">{chatError}</p>
              <button
                type="button"
                onClick={retryLastDraft}
                className="shrink-0 cursor-pointer rounded-md border border-destructive/40 px-2 py-1 text-destructive transition hover:bg-destructive/10"
              >
                Retry
              </button>
            </div>
          )}
          {voiceError && (
            <p
              className="mx-auto mb-2 max-w-3xl text-xs text-destructive"
              role="status"
            >
              {voiceError}
            </p>
          )}
          {demoBanner && (
            <p
              className="mb-2 text-center text-xs text-accent sm:hidden"
              role="status"
            >
              Preview mode — live models offline
            </p>
          )}
          <div className="mx-auto flex max-w-3xl items-end gap-2 sm:gap-3">
            <div className="relative min-w-0 flex-1">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => onInputChange(e.target.value)}
                onKeyDown={onKeyDown}
                rows={2}
                maxLength={2000}
                placeholder={
                  recording
                    ? 'Listening… tap mic again to send'
                    : `Message ${character.shortName}…`
                }
                aria-label="Your message"
                disabled={recording}
                className={`min-h-12 max-h-36 w-full resize-none overflow-y-auto rounded-xl border bg-card px-4 py-3 text-base leading-relaxed text-foreground transition-[border-color,box-shadow] duration-200 placeholder:text-muted-fg focus:border-accent/55 disabled:opacity-80 sm:text-sm ${
                  recording
                    ? 'composer-listen border-accent/45'
                    : 'border-white/10'
                }`}
              />
              {input.length >= 1800 && (
                <span className="pointer-events-none absolute bottom-2 right-3 text-[0.65rem] tabular-nums text-muted-fg">
                  {input.length}/2000
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={toggleMic}
              disabled={loading}
              aria-pressed={recording}
              aria-label={
                recording ? 'Stop recording and send' : 'Start voice input'
              }
              title={
                speechOk.recognition
                  ? recording
                    ? 'Stop & send'
                    : 'Tap to talk'
                  : 'Voice unsupported in this browser'
              }
              className={`inline-flex h-12 w-12 shrink-0 cursor-pointer items-center justify-center rounded-xl border transition duration-200 active:scale-[0.97] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-40 ${
                recording
                  ? 'mic-recording border-accent bg-accent/20 text-accent'
                  : speechOk.recognition
                    ? 'border-white/10 bg-card text-foreground hover:border-accent/40 hover:text-accent hover:shadow-[0_0_20px_-6px_oklch(0.7_0.12_75_/_0.45)]'
                    : 'border-white/10 bg-card text-muted-fg'
              }`}
            >
              {recording ? (
                <span className="mic-bars" aria-hidden>
                  <span />
                  <span />
                  <span />
                  <span />
                </span>
              ) : (
                <Mic className="h-4 w-4" aria-hidden />
              )}
            </button>
            <ClickSpark
              sparkColor={character.accent}
              sparkSize={7}
              sparkRadius={20}
              sparkCount={9}
              duration={360}
              className="shrink-0"
            >
              <button
                type="button"
                onClick={handleSend}
                disabled={loading || recording || !input.trim()}
                className="btn-sheen relative z-0 inline-flex h-12 w-12 cursor-pointer items-center justify-center rounded-xl bg-accent text-on-accent shadow-[0_10px_24px_-10px_oklch(0.55_0.14_75_/_0.55)] transition duration-200 hover:brightness-110 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
                aria-label="Send message"
              >
                <Send className="h-4 w-4" aria-hidden />
              </button>
            </ClickSpark>
          </div>
        </div>
      </main>
    </div>
  )
}
