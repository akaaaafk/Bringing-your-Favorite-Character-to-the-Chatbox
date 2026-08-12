/** Free browser TTS prefs — not licensed actor likenesses. */
export interface VoiceProfile {
  /** Prefer matching OS/browser voice names (case-insensitive substrings). */
  prefer: string[]
  gender: 'male' | 'female'
  rate: number
  pitch: number
}

/** Character card metadata for the React UI. */
export interface Character {
  id: string
  name: string
  shortName: string
  film: string
  desc: string
  example: string
  accent: string
  glow: string
  /** Initials shown on avatar fallback glyph */
  monogram: string
  /** Hue hint for portrait wash (0–360) */
  portraitHue: number
  slug: string
  /** Actor portrait under /public/avatars (see avatars/README.md) */
  avatar: string
  voice: VoiceProfile
}

export const CHARACTERS: Character[] = [
  {
    id: 'ALVY',
    name: 'Alvy Singer',
    shortName: 'Alvy',
    film: 'Annie Hall',
    desc: 'Neurotic, self-deprecating, rambling, breaks the fourth wall.',
    example: "I-I think I forgot something. Did I already say that? Never mind.",
    accent: '#6B8EAD',
    glow: 'rgba(107, 142, 173, 0.32)',
    monogram: 'AS',
    portraitHue: 210,
    slug: 'alvy',
    avatar: '/avatars/alvy.jpg',
    voice: {
      prefer: ['Google US English', 'Microsoft Mark', 'Alex', 'Daniel'],
      gender: 'male',
      rate: 1.05,
      pitch: 1.12,
    },
  },
  {
    id: 'JACK',
    name: 'Jack',
    shortName: 'Jack',
    film: 'Fight Club',
    desc: 'Cynical, nihilistic, deadpan narrator.',
    example: 'I am Jack\'s complete lack of surprise.',
    accent: '#B85C38',
    glow: 'rgba(184, 92, 56, 0.32)',
    monogram: 'JK',
    portraitHue: 25,
    slug: 'jack',
    avatar: '/avatars/jack.jpg',
    voice: {
      prefer: ['Microsoft David', 'Google UK English Male', 'Fred', 'Bruce'],
      gender: 'male',
      rate: 0.95,
      pitch: 0.88,
    },
  },
  {
    id: 'BATEMAN',
    name: 'Patrick Bateman',
    shortName: 'Bateman',
    film: 'American Psycho',
    desc: 'Clinical, materialistic, obsessive, deadpan.',
    example: 'I have to return some videotapes.',
    accent: '#C4B59A',
    glow: 'rgba(196, 181, 154, 0.28)',
    monogram: 'PB',
    portraitHue: 70,
    slug: 'bateman',
    avatar: '/avatars/bateman.jpg',
    voice: {
      prefer: ['Microsoft Guy', 'Google US English', 'Tom', 'Ralph'],
      gender: 'male',
      rate: 1,
      pitch: 0.95,
    },
  },
  {
    id: 'BEN',
    name: 'Benjamin Braddock',
    shortName: 'Ben',
    film: 'The Graduate',
    desc: 'Awkward, hesitant, passive.',
    example: 'Mrs. Robinson, you\'re trying to seduce me. Aren\'t you?',
    accent: '#7A9B76',
    glow: 'rgba(122, 155, 118, 0.28)',
    monogram: 'BB',
    portraitHue: 130,
    slug: 'ben',
    avatar: '/avatars/ben.jpg',
    voice: {
      prefer: ['Microsoft Andrew', 'Google UK English Male', 'Junior', 'Sam'],
      gender: 'male',
      rate: 0.95,
      pitch: 1.05,
    },
  },
  {
    id: 'ERIN',
    name: 'Erin Brockovich',
    shortName: 'Erin',
    film: 'Erin Brockovich',
    desc: 'Blunt, confrontational, sassy.',
    example: "They're calling it a contaminant. I call it poison.",
    accent: '#C45C4A',
    glow: 'rgba(196, 92, 74, 0.32)',
    monogram: 'EB',
    portraitHue: 20,
    slug: 'erin',
    avatar: '/avatars/erin.jpg',
    voice: {
      prefer: [
        'Microsoft Zira',
        'Google US English Female',
        'Samantha',
        'Karen',
        'Susan',
      ],
      gender: 'female',
      rate: 1.05,
      pitch: 1.08,
    },
  },
]
