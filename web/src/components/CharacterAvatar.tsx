import type { Character } from '../data/characters'

export type AvatarMood = 'idle' | 'listening' | 'speaking'

interface CharacterAvatarProps {
  character: Character
  size?: 'sm' | 'md' | 'lg'
  mood?: AvatarMood
  className?: string
  /** When true, expose name to assistive tech (header / empty state). */
  labelled?: boolean
}

const SIZE = {
  sm: 'h-10 w-10',
  md: 'h-14 w-14',
  lg: 'h-20 w-20 sm:h-24 sm:w-24',
} as const

export function CharacterAvatar({
  character,
  size = 'md',
  mood = 'idle',
  className = '',
  labelled = false,
}: CharacterAvatarProps) {
  const ring =
    mood === 'listening'
      ? 'avatar-ring-listen'
      : mood === 'speaking'
        ? 'avatar-ring-speak'
        : ''

  const status =
    mood === 'listening'
      ? 'Listening'
      : mood === 'speaking'
        ? 'Speaking'
        : undefined

  return (
    <div
      className={`relative shrink-0 overflow-hidden rounded-full ${SIZE[size]} ${className}`}
      {...(labelled
        ? {
            role: 'img',
            'aria-label': status
              ? `${character.name}, ${status}`
              : character.name,
          }
        : { 'aria-hidden': true })}
    >
      <div
        className={`pointer-events-none absolute inset-0 z-10 rounded-full ${ring}`}
        style={{
          boxShadow:
            mood !== 'idle'
              ? `0 0 0 2px color-mix(in oklab, ${character.accent} 75%, transparent), 0 8px 24px -10px ${character.glow}`
              : `0 0 0 1px color-mix(in oklab, ${character.accent} 40%, transparent)`,
        }}
      />
      <img
        src={character.avatar}
        alt=""
        width={96}
        height={96}
        className={`h-full w-full rounded-full object-cover object-top ${
          mood === 'speaking' ? 'avatar-speak-glow' : ''
        }`}
        draggable={false}
        loading="lazy"
        decoding="async"
      />
      {mood === 'speaking' && (
        <span
          className="avatar-mouth-bar pointer-events-none absolute bottom-[16%] left-1/2 z-20 h-1 w-[42%] -translate-x-1/2 rounded-full opacity-90"
          style={{ background: character.accent }}
        />
      )}
      {mood === 'listening' && (
        <span className="avatar-listen-dot absolute bottom-0.5 left-1/2 z-20 h-2 w-2 -translate-x-1/2 rounded-full bg-accent" />
      )}
    </div>
  )
}
