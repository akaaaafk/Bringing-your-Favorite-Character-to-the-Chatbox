import { apiUrl } from './apiBase'

export type SpeechSupport = {
  recognition: boolean
  synthesis: boolean
}

export function getSpeechSupport(): SpeechSupport {
  if (typeof window === 'undefined') {
    return { recognition: false, synthesis: false }
  }
  const SpeechRecognitionCtor =
    window.SpeechRecognition ?? window.webkitSpeechRecognition
  // Neural TTS uses HTMLAudioElement; speechSynthesis is only the fallback.
  const canPlayAudio = typeof Audio !== 'undefined'
  return {
    recognition: Boolean(SpeechRecognitionCtor),
    synthesis: canPlayAudio || 'speechSynthesis' in window,
  }
}

type RecognitionCtor = new () => SpeechRecognition

function getRecognitionCtor(): RecognitionCtor | null {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null
}

function describeNetworkError(): string {
  const ua = typeof navigator !== 'undefined' ? navigator.userAgent : ''
  const isEdge = /Edg\//.test(ua)
  const isBrave = /Brave/i.test(ua) || !!(navigator as Navigator & { brave?: unknown }).brave
  const isChrome = /Chrome\//.test(ua) && !isEdge && !isBrave

  if (isEdge) {
    return 'Edge often cannot reach Google’s speech cloud (reports “network”). Open this app in Google Chrome, or type instead.'
  }
  if (isBrave) {
    return 'Brave does not include Google’s speech service. Use Google Chrome, or type instead.'
  }
  if (!isChrome) {
    return 'This browser’s speech cloud is unavailable. Try Google Chrome on http://localhost, or type instead.'
  }
  return 'Chrome speech cloud unreachable (not our API). Confirm mic permission, try https://www.google.com/chrome/demos/speech.html, or type instead.'
}

export type ToggleListenHandlers = {
  onInterim?: (text: string) => void
  onFinal: (text: string) => void
  onError: (message: string) => void
  onStart?: () => void
  onEnd?: () => void
}

/** Tap-to-toggle speech recognition (start / stop). */
export function createToggleListener(handlers: ToggleListenHandlers) {
  const Ctor = getRecognitionCtor()
  if (!Ctor) {
    return {
      supported: false as const,
      start: () =>
        handlers.onError(
          'Voice input is not supported in this browser. Use Google Chrome, or type instead.',
        ),
      stop: () => {},
      abort: () => {},
    }
  }

  let recognition: SpeechRecognition | null = null
  let running = false
  let finalBuffer = ''
  let lastLive = ''
  let errored = false
  let stopping = false

  function tearDown() {
    if (!recognition) return
    recognition.onstart = null
    recognition.onresult = null
    recognition.onerror = null
    recognition.onend = null
    try {
      recognition.abort()
    } catch {
      /* ignore */
    }
    recognition = null
  }

  function wire(rec: SpeechRecognition) {
    rec.continuous = true
    rec.interimResults = true
    rec.lang = 'en-US'

    rec.onstart = () => {
      running = true
      errored = false
      stopping = false
      finalBuffer = ''
      lastLive = ''
      handlers.onStart?.()
    }

    rec.onresult = (event: SpeechRecognitionEvent) => {
      let interim = ''
      let finalized = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const piece = event.results[i][0]?.transcript ?? ''
        if (event.results[i].isFinal) finalized += piece
        else interim += piece
      }
      if (finalized) finalBuffer = `${finalBuffer} ${finalized}`.trim()
      lastLive = `${finalBuffer} ${interim}`.trim()
      if (lastLive) handlers.onInterim?.(lastLive)
    }

    rec.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === 'aborted') return
      // User-initiated stop can race a no-speech / network blip — ignore if we already have text.
      if (stopping && (event.error === 'no-speech' || event.error === 'network')) {
        return
      }
      errored = true
      console.warn('[speech] recognition error:', event.error)
      const map: Record<string, string> = {
        'not-allowed': 'Microphone permission denied. You can still type.',
        'no-speech': 'No speech detected. Tap the mic and try again.',
        network: describeNetworkError(),
        'audio-capture': 'No microphone found.',
        'service-not-allowed':
          'Speech service blocked by the browser. Try Google Chrome, or type instead.',
      }
      handlers.onError(map[event.error] ?? `Voice error: ${event.error}`)
    }

    rec.onend = () => {
      const wasRunning = running
      running = false
      handlers.onEnd?.()
      recognition = null
      if (!wasRunning) return
      if (errored) {
        errored = false
        finalBuffer = ''
        lastLive = ''
        stopping = false
        return
      }
      const text = (finalBuffer || lastLive).trim()
      finalBuffer = ''
      lastLive = ''
      stopping = false
      if (text) handlers.onFinal(text)
      else handlers.onError('No speech detected. Tap the mic and try again.')
    }
  }

  return {
    supported: true as const,
    start: () => {
      try {
        tearDown()
        finalBuffer = ''
        lastLive = ''
        errored = false
        stopping = false
        recognition = new Ctor()
        wire(recognition)
        recognition.start()
      } catch (err) {
        console.warn('[speech] start failed:', err)
        handlers.onError('Could not start the microphone. Try again.')
      }
    },
    stop: () => {
      stopping = true
      try {
        recognition?.stop()
      } catch {
        /* already stopped */
      }
    },
    abort: () => {
      errored = true
      stopping = true
      running = false
      finalBuffer = ''
      lastLive = ''
      tearDown()
    },
  }
}

export type SpeakVoiceOpts = {
  /** Character id / tag for neural TTS (e.g. ALVY / alvy). */
  character?: string
  prefer?: string[]
  gender?: 'male' | 'female'
  rate?: number
  pitch?: number
  onStart?: () => void
  onEnd?: () => void
  /** Autoplay blocked (common on mobile after async chat). */
  onBlocked?: () => void
}

const FEMALE_HINTS =
  /\b(zira|susan|samantha|karen|hazel|aria|jenny|michelle|linda|helen|female|woman)\b/i
const MALE_HINTS =
  /\b(david|mark|guy|andrew|james|george|fred|bruce|daniel|alex|tom|ralph|junior|sam|male|man)\b/i

let currentAudio: HTMLAudioElement | null = null
let currentObjectUrl: string | null = null
let currentMediaSource: MediaSource | null = null
let currentAbort: AbortController | null = null
let speakGeneration = 0
let audioUnlocked = false

const MSE_MP3 = 'audio/mpeg'
/** Minimal silent WAV — unlocks HTMLAudioElement inside a user gesture. */
const SILENT_WAV =
  'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA='

function isAppleTouch(): boolean {
  if (typeof navigator === 'undefined') return false
  return (
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  )
}

/**
 * Call from a tap/click (Send, mic, unmute). Mobile browsers block audio.play()
 * that starts only after an async fetch unless unlocked in a gesture.
 */
export function unlockAudioPlayback(): void {
  if (typeof window === 'undefined' || audioUnlocked) return
  try {
    const AC =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext
    if (AC) {
      const ctx = new AC()
      void ctx.resume().finally(() => {
        void ctx.close().catch(() => {})
      })
    }
  } catch {
    /* ignore */
  }
  try {
    const probe = new Audio(SILENT_WAV)
    prepareAudioElement(probe)
    void probe
      .play()
      .then(() => {
        audioUnlocked = true
        probe.pause()
      })
      .catch(() => {
        /* still try later; onBlocked may surface a tap-to-hear */
      })
  } catch {
    /* ignore */
  }
}

function prepareAudioElement(audio: HTMLAudioElement) {
  audio.setAttribute('playsinline', 'true')
  audio.setAttribute('webkit-playsinline', 'true')
  ;(audio as HTMLAudioElement & { playsInline?: boolean }).playsInline = true
  audio.preload = 'auto'
}

function isAutoplayBlocked(err: unknown): boolean {
  const name = (err as { name?: string })?.name
  if (name === 'NotAllowedError' || name === 'AbortError') return name === 'NotAllowedError'
  const msg = String((err as { message?: string })?.message ?? err)
  return /NotAllowedError|user didn't interact|user gesture|play\(\) failed/i.test(msg)
}

function canStreamMpeg(): boolean {
  // iOS Safari: MSE + audio/mpeg is unreliable; prefer full blob playback.
  if (isAppleTouch()) return false
  return (
    typeof MediaSource !== 'undefined' &&
    typeof MediaSource.isTypeSupported === 'function' &&
    MediaSource.isTypeSupported(MSE_MP3)
  )
}

function stopNeuralAudio(opts?: { keepAbort?: boolean }) {
  if (!opts?.keepAbort) {
    currentAbort?.abort()
    currentAbort = null
  }
  if (currentAudio) {
    currentAudio.onplay = null
    currentAudio.onended = null
    currentAudio.onerror = null
    try {
      currentAudio.pause()
    } catch {
      /* ignore */
    }
    currentAudio.removeAttribute('src')
    currentAudio.load()
    currentAudio = null
  }
  if (currentMediaSource) {
    try {
      if (currentMediaSource.readyState === 'open') {
        currentMediaSource.endOfStream()
      }
    } catch {
      /* ignore */
    }
    currentMediaSource = null
  }
  if (currentObjectUrl) {
    URL.revokeObjectURL(currentObjectUrl)
    currentObjectUrl = null
  }
}

function scoreVoice(
  voice: SpeechSynthesisVoice,
  prefer: string[],
  gender: 'male' | 'female' | undefined,
): number {
  const name = voice.name
  let score = 0
  if (/^en(-|_)/i.test(voice.lang) || voice.lang.toLowerCase() === 'en') {
    score += 40
  } else if (/^en/i.test(voice.lang)) {
    score += 25
  } else {
    return -1000
  }
  if (voice.localService) score += 8
  for (let i = 0; i < prefer.length; i++) {
    if (name.toLowerCase().includes(prefer[i].toLowerCase())) {
      score += 100 - i * 8
      break
    }
  }
  if (gender === 'female') {
    if (FEMALE_HINTS.test(name)) score += 35
    if (MALE_HINTS.test(name)) score -= 40
  } else if (gender === 'male') {
    if (MALE_HINTS.test(name)) score += 35
    if (FEMALE_HINTS.test(name)) score -= 40
  }
  return score
}

function pickVoice(
  prefer: string[],
  gender?: 'male' | 'female',
): SpeechSynthesisVoice | null {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return null
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null
  let best: SpeechSynthesisVoice | null = null
  let bestScore = -Infinity
  for (const voice of voices) {
    const s = scoreVoice(voice, prefer, gender)
    if (s > bestScore) {
      bestScore = s
      best = voice
    }
  }
  return bestScore > -500 ? best : null
}

function speakBrowser(text: string, opts?: SpeakVoiceOpts): void {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
    opts?.onEnd?.()
    return
  }

  const run = () => {
    window.speechSynthesis.cancel()
    const utter = new SpeechSynthesisUtterance(text)
    utter.rate = opts?.rate ?? 1
    utter.pitch = opts?.pitch ?? 1
    utter.lang = 'en-US'
    const voice = pickVoice(opts?.prefer ?? [], opts?.gender)
    if (voice) {
      utter.voice = voice
      utter.lang = voice.lang || 'en-US'
    }
    let started = false
    utter.onstart = () => {
      started = true
      opts?.onStart?.()
    }
    utter.onend = () => opts?.onEnd?.()
    utter.onerror = () => {
      if (!started) finishBlocked(opts)
      else opts?.onEnd?.()
    }
    window.speechSynthesis.speak(utter)
  }

  if (window.speechSynthesis.getVoices().length > 0) {
    run()
    return
  }

  let spoken = false
  const onVoices = () => {
    if (spoken) return
    spoken = true
    window.speechSynthesis.removeEventListener('voiceschanged', onVoices)
    run()
  }
  window.speechSynthesis.addEventListener('voiceschanged', onVoices)
  window.setTimeout(onVoices, 250)
}

async function playMpegBlob(
  blob: Blob,
  opts?: SpeakVoiceOpts,
  generation?: number,
): Promise<void> {
  if (generation !== undefined && generation !== speakGeneration) return
  stopNeuralAudio({ keepAbort: true })
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel()
  }
  const url = URL.createObjectURL(blob)
  currentObjectUrl = url
  const audio = new Audio(url)
  prepareAudioElement(audio)
  currentAudio = audio
  await new Promise<void>((resolve, reject) => {
    audio.onended = () => {
      stopNeuralAudio()
      opts?.onEnd?.()
      resolve()
    }
    audio.onerror = () => {
      stopNeuralAudio()
      reject(new Error('audio playback failed'))
    }
    audio.onplay = () => {
      audioUnlocked = true
      opts?.onStart?.()
    }
    void audio.play().catch(reject)
  })
}

async function playMpegStream(
  res: Response,
  opts?: SpeakVoiceOpts,
  generation?: number,
): Promise<void> {
  if (!res.body) throw new Error('no response body')
  if (generation !== undefined && generation !== speakGeneration) return

  stopNeuralAudio({ keepAbort: true })
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel()
  }

  const mediaSource = new MediaSource()
  currentMediaSource = mediaSource
  const url = URL.createObjectURL(mediaSource)
  currentObjectUrl = url
  const audio = new Audio()
  prepareAudioElement(audio)
  currentAudio = audio
  audio.src = url

  await new Promise<void>((resolve, reject) => {
    let settled = false
    const fail = (err: unknown) => {
      if (settled) return
      settled = true
      stopNeuralAudio()
      reject(err instanceof Error ? err : new Error(String(err)))
    }
    const succeed = () => {
      if (settled) return
      settled = true
      stopNeuralAudio()
      opts?.onEnd?.()
      resolve()
    }

    audio.onended = () => succeed()
    audio.onerror = () => fail(new Error('audio playback failed'))

    mediaSource.addEventListener('sourceopen', () => {
      let sb: SourceBuffer
      try {
        sb = mediaSource.addSourceBuffer(MSE_MP3)
      } catch (err) {
        fail(err)
        return
      }

      const queue: Uint8Array[] = []
      let streamDone = false
      let started = false

      const pump = () => {
        if (generation !== undefined && generation !== speakGeneration) return
        if (sb.updating || queue.length === 0) {
          if (!sb.updating && streamDone && queue.length === 0) {
            try {
              if (mediaSource.readyState === 'open') mediaSource.endOfStream()
            } catch {
              /* ignore */
            }
          }
          return
        }
        const next = queue.shift()
        if (!next) return
        try {
          sb.appendBuffer(new Uint8Array(next))
        } catch (err) {
          fail(err)
        }
      }

      sb.addEventListener('updateend', () => {
        if (!started && audio.paused) {
          started = true
          void audio.play().then(() => {
            audioUnlocked = true
            opts?.onStart?.()
          }).catch(fail)
        }
        pump()
      })
      sb.addEventListener('error', () => fail(new Error('sourceBuffer error')))

      const reader = res.body!.getReader()
      ;(async () => {
        try {
          for (;;) {
            const { done, value } = await reader.read()
            if (generation !== undefined && generation !== speakGeneration) {
              await reader.cancel()
              return
            }
            if (done) {
              streamDone = true
              pump()
              return
            }
            if (value?.byteLength) {
              queue.push(value)
              pump()
            }
          }
        } catch (err) {
          if ((err as { name?: string })?.name === 'AbortError') return
          fail(err)
        }
      })()
    })
  })
}

async function speakNeural(
  text: string,
  character: string,
  opts?: SpeakVoiceOpts,
  generation?: number,
): Promise<boolean> {
  const abort = new AbortController()
  currentAbort = abort
  const res = await fetch(apiUrl('/api/tts'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, character }),
    signal: abort.signal,
  })
  if (!res.ok) return false
  if (generation !== undefined && generation !== speakGeneration) return true

  try {
    if (canStreamMpeg() && res.body) {
      await playMpegStream(res, opts, generation)
      return true
    }
    const blob = await res.blob()
    if (!blob.size) return false
    await playMpegBlob(blob, opts, generation)
    return true
  } catch (err) {
    if ((err as { name?: string })?.name === 'AbortError') return true
    throw err
  }
}

function finishBlocked(opts?: SpeakVoiceOpts) {
  opts?.onEnd?.()
  opts?.onBlocked?.()
}

/**
 * Prefer free Edge neural TTS (/api/tts); fall back to browser speechSynthesis.
 * Speaking UI starts when playback actually begins (or immediately for browser TTS).
 */
export function speakText(text: string, opts?: SpeakVoiceOpts): void {
  const trimmed = text.trim()
  if (!trimmed) {
    opts?.onEnd?.()
    return
  }

  const generation = ++speakGeneration
  stopNeuralAudio()
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel()
  }

  const character = opts?.character?.trim()
  if (!character) {
    speakBrowser(trimmed, opts)
    return
  }

  const playOpts: SpeakVoiceOpts = { ...opts }

  void speakNeural(trimmed, character, playOpts, generation)
    .then((ok) => {
      if (generation !== speakGeneration) return
      if (!ok) speakBrowser(trimmed, playOpts)
    })
    .catch((err) => {
      if (generation !== speakGeneration) return
      if (isAutoplayBlocked(err)) {
        finishBlocked(playOpts)
        return
      }
      try {
        speakBrowser(trimmed, playOpts)
      } catch {
        finishBlocked(playOpts)
      }
    })
}

export function cancelSpeech() {
  speakGeneration += 1
  stopNeuralAudio()
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel()
  }
}
