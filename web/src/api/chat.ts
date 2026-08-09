export interface ChatRequest {
  message: string
  character: string
  n_candidates: number
  use_rerank: boolean
}

export interface ChatResponse {
  reply: string
  persona_score: number | null
  n_candidates: number
  mode: 'live' | 'demo'
}

const DEMO_LINES: Record<string, string[]> = {
  ALVY: [
    "I-I don't know. Maybe I'm overthinking this. Am I overthinking this?",
    "That's great. That is... that is really great. For you. I guess.",
    "Can we talk about this? Not now — later. Or now. I don't know.",
  ],
  JACK: [
    "I am Jack's smirking revenge.",
    "The things you own end up owning you.",
    "This is your life, and it's ending one minute at a time.",
  ],
  BATEMAN: [
    'I have to return some videotapes.',
    'There is an idea of a Patrick Bateman. Some kind of abstraction.',
    'I need to know the details of the reservation. The details.',
  ],
  BEN: [
    "I just... I don't know what I'm going to do with my life.",
    "Are you... are you trying to tell me something?",
    "Plastics. Wait — what? No. I mean... yes? I don't know.",
  ],
  ERIN: [
    "They're calling it a contaminant. I call it poison.",
    "I may not have a law degree, but I know when something stinks.",
    "Don't talk to me like I'm stupid. I'm not stupid.",
  ],
}

function demoReply(character: string, message: string, nCandidates: number): ChatResponse {
  const lines = DEMO_LINES[character] ?? [
    'The reel is spinning. Train the models to hear a truer voice.',
  ]
  const idx =
    Math.abs(
      [...message].reduce((a, c) => a + c.charCodeAt(0), 0) +
        character.length,
    ) % lines.length
  return {
    reply: lines[idx],
    persona_score: null,
    n_candidates: nCandidates,
    mode: 'demo',
  }
}

export async function sendChat(req: ChatRequest): Promise<ChatResponse> {
  let res: Response
  try {
    res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  } catch {
    // API unreachable — offline demo only
    return demoReply(req.character, req.message, req.n_candidates)
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      /* keep status text */
    }
    throw new Error(detail)
  }

  const data = (await res.json()) as ChatResponse
  return { ...data, mode: data.mode ?? 'live' }
}
