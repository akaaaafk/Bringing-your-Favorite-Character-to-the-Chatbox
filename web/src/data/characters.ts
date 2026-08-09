/** Synthetic stylized portraits — not licensed likenesses. */
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
  /** Cinematic portrait under /public/avatars */
  avatar: string
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
  },
]
