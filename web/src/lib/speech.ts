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
  return {
    recognition: Boolean(SpeechRecognitionCtor),
    synthesis: 'speechSynthesis' in window,
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

export function speakText(
  text: string,
  opts?: {
    onStart?: () => void
    onEnd?: () => void
    rate?: number
    pitch?: number
  },
): void {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
    opts?.onEnd?.()
    return
  }

  window.speechSynthesis.cancel()
  const utter = new SpeechSynthesisUtterance(text)
  utter.rate = opts?.rate ?? 1
  utter.pitch = opts?.pitch ?? 1
  utter.lang = 'en-US'
  utter.onstart = () => opts?.onStart?.()
  utter.onend = () => opts?.onEnd?.()
  utter.onerror = () => opts?.onEnd?.()
  window.speechSynthesis.speak(utter)
}

export function cancelSpeech() {
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel()
  }
}
