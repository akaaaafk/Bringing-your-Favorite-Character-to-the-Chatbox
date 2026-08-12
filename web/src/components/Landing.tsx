import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { ArrowRight, Clapperboard } from 'lucide-react'
import { CHARACTERS, type Character } from '../data/characters'
import BlurText from './react-bits/BlurText'
import ClickSpark from './react-bits/ClickSpark'
import { CharacterAvatar } from './CharacterAvatar'
import LightRays from './react-bits/LightRays'

interface LandingProps {
  onEnter: (character: Character) => void
  resume?: {
    character: Character
    onResume: () => void
  }
}

export function Landing({ onEnter, resume }: LandingProps) {
  const castRef = useRef<HTMLUListElement>(null)
  const [reduceMotion, setReduceMotion] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReduceMotion(mq.matches)
    const onChange = () => setReduceMotion(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  useEffect(() => {
    const root = castRef.current
    if (!root) return
    const items = root.querySelectorAll('.cast-in')
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible')
            io.unobserve(entry.target)
          }
        }
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.12 },
    )
    items.forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [])

  return (
    <div className="view-fade relative min-h-dvh overflow-x-hidden bg-background">
      <div className="letterbox-bar letterbox-top" aria-hidden />
      <div className="letterbox-bar letterbox-bottom" aria-hidden />

      <section className="relative flex min-h-dvh flex-col justify-end px-5 pb-16 pt-10 sm:px-10 sm:pb-24 sm:pt-14 lg:px-16 lg:pb-28">
        <div className="film-perforation film-perforation-left hidden sm:block" aria-hidden />
        <div className="film-perforation film-perforation-right hidden sm:block" aria-hidden />

        <div
          className="absolute inset-0"
          style={{
            background:
              'radial-gradient(ellipse 75% 58% at 70% 10%, oklch(0.62 0.13 75 / 0.28), transparent 55%), radial-gradient(ellipse 48% 42% at 12% 88%, oklch(0.4 0.06 40 / 0.32), transparent 50%), linear-gradient(168deg, oklch(0.14 0.022 52) 0%, oklch(0.17 0.02 55) 46%, oklch(0.2 0.03 42) 100%)',
          }}
        />
        {!reduceMotion && (
          <div
            className="pointer-events-none absolute inset-0 opacity-60"
            aria-hidden
          >
            <LightRays
              raysOrigin="top-center"
              raysColor="#C9A962"
              raysSpeed={0.42}
              lightSpread={0.65}
              rayLength={2.7}
              fadeDistance={1.2}
              saturation={0.85}
              noiseAmount={0.16}
              followMouse
              mouseInfluence={0.1}
              className="absolute inset-0"
            />
          </div>
        )}
        <div
          className="ambient-blob left-[-14%] top-[6%] h-80 w-80"
          style={{ background: 'oklch(0.7 0.14 75)' }}
          aria-hidden
        />
        <div
          className="ambient-blob right-[-10%] bottom-[12%] h-[26rem] w-[26rem]"
          style={{
            background: 'oklch(0.42 0.08 40)',
            animationDelay: '-7s',
          }}
          aria-hidden
        />
        <div
          className="film-grain film-flicker pointer-events-none absolute inset-0 mix-blend-overlay"
          aria-hidden
        />
        <div className="film-scratch pointer-events-none absolute inset-0" aria-hidden />
        <div className="film-vignette pointer-events-none absolute inset-0" aria-hidden />

        {/* Poster cast cluster */}
        <div className="hero-reveal-late pointer-events-none absolute right-6 top-[16%] z-[5] hidden w-[min(44vw,26rem)] lg:block xl:right-16">
          <div className="gate-weave relative h-[26rem]">
            {CHARACTERS.map((c, i) => (
              <button
                key={c.id}
                type="button"
                onClick={() => onEnter(c)}
                className="cast-stack pointer-events-auto absolute cursor-pointer rounded-full transition duration-300 hover:z-20 hover:scale-110 focus-visible:z-20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
                style={{
                  left: `${i * 15}%`,
                  top: `${(i % 3) * 16}%`,
                  zIndex: 10 - i,
                  animationDelay: `${0.35 + i * 0.08}s`,
                  filter: 'contrast(1.08) saturate(0.9)',
                }}
                aria-label={`Chat with ${c.shortName}`}
              >
                <span className="block scale-110 drop-shadow-[0_18px_40px_oklch(0.05_0.02_50_/_0.75)]">
                  <CharacterAvatar character={c} size="lg" />
                </span>
              </button>
            ))}
          </div>
          <p className="mt-3 text-right font-serif text-base italic tracking-wide text-muted-fg">
            Now playing
          </p>
        </div>

        <header className="hero-reveal-late relative z-10 mb-auto flex items-center gap-3 pt-1 safe-header-pad sm:gap-3.5 sm:pt-4">
          <span className="flex h-11 w-11 items-center justify-center rounded-full border border-accent/35 bg-card/70 text-accent shadow-[0_0_28px_-6px_oklch(0.55_0.12_75_/_0.5)] sm:h-12 sm:w-12">
            <Clapperboard className="h-5 w-5" strokeWidth={1.5} aria-hidden />
          </span>
          <p className="font-serif text-xl tracking-[0.01em] text-foreground sm:text-3xl">
            Movie Persona Chat
          </p>
        </header>

        <div className="relative z-10 max-w-[14ch] sm:max-w-2xl lg:max-w-3xl">
          <div className="gate-weave">
            <BlurText
              as="h1"
              text="Five roles. Your cue."
              animateBy="words"
              delay={130}
              stepDuration={0.36}
              direction="bottom"
              className="poster-title font-serif text-[2.55rem] font-medium leading-[0.94] tracking-[-0.04em] text-foreground sm:text-6xl lg:text-[5.5rem] xl:text-[6rem]"
              animationFrom={{ filter: 'blur(16px)', opacity: 0, y: 36 }}
              animationTo={[
                { filter: 'blur(6px)', opacity: 0.55, y: 12 },
                { filter: 'blur(0px)', opacity: 1, y: 0 },
              ]}
              easing={[0.16, 1, 0.3, 1]}
            />
          </div>
          <p className="hero-reveal-cta mt-4 max-w-md text-[0.95rem] leading-relaxed text-muted-fg sm:mt-6 sm:text-lg">
            Chat with film voices that stay in character.
          </p>
          <div className="hero-reveal-cta mt-7 flex flex-col items-stretch gap-3 sm:mt-10 sm:flex-row sm:flex-wrap sm:items-center sm:gap-6">
            <ClickSpark
              sparkColor="#C9A962"
              sparkSize={10}
              sparkRadius={28}
              sparkCount={14}
              duration={460}
              className="inline-flex w-full sm:w-auto"
            >
              <button
                type="button"
                onClick={() => {
                  const reduce = window.matchMedia(
                    '(prefers-reduced-motion: reduce)',
                  ).matches
                  document.getElementById('cast')?.scrollIntoView({
                    behavior: reduce ? 'auto' : 'smooth',
                    block: 'start',
                  })
                }}
                className="btn-sheen group relative z-0 inline-flex min-h-12 w-full cursor-pointer items-center justify-center gap-3 rounded-full bg-accent px-8 py-3.5 text-[0.95rem] font-semibold tracking-wide text-on-accent shadow-[0_18px_48px_-10px_oklch(0.45_0.12_75_/_0.7)] transition duration-200 hover:brightness-110 active:scale-[0.97] sm:w-auto sm:px-9 sm:py-4"
              >
                Choose a voice
                <ArrowRight
                  className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5"
                  aria-hidden
                />
              </button>
            </ClickSpark>
            {resume ? (
              <button
                type="button"
                onClick={resume.onResume}
                className="inline-flex min-h-11 cursor-pointer items-center justify-center rounded-lg px-3 text-sm tracking-wide text-muted-fg underline-offset-4 transition duration-200 hover:text-foreground hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring sm:justify-start sm:px-0"
              >
                Continue with {resume.character.shortName}
              </button>
            ) : null}
            <a
              href="#cast"
              className="inline-flex min-h-11 cursor-pointer items-center justify-center rounded-lg px-3 text-sm tracking-wide text-muted-fg underline-offset-4 transition duration-200 hover:text-foreground hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring sm:justify-start sm:px-0"
            >
              Meet the cast
            </a>
          </div>
        </div>

        <div className="hero-reveal-cta relative z-10 mt-8 flex lg:hidden">
          <div className="flex flex-wrap items-center gap-2.5">
            {CHARACTERS.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => onEnter(c)}
                className="inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded-full ring-2 ring-background transition hover:z-10 hover:scale-105 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                aria-label={`Chat with ${c.shortName}`}
                style={{ filter: 'contrast(1.08) saturate(0.9)' }}
              >
                <CharacterAvatar character={c} size="md" />
              </button>
            ))}
          </div>
        </div>
      </section>

      <section
        id="cast"
        aria-labelledby="cast-heading"
        className="relative scroll-mt-8 border-t border-white/5 bg-background px-5 py-14 sm:px-10 sm:py-24 lg:px-16 lg:pb-32"
      >
        <div
          className="film-grain pointer-events-none absolute inset-0 opacity-30 mix-blend-overlay"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-48"
          style={{
            background:
              'linear-gradient(180deg, oklch(0.4 0.08 75 / 0.08), transparent)',
          }}
          aria-hidden
        />
        <div className="relative mx-auto max-w-6xl">
          <h2
            id="cast-heading"
            className="poster-title font-serif text-4xl tracking-[-0.03em] text-foreground sm:text-5xl lg:text-6xl"
          >
            The cast
          </h2>
          <p className="mt-3 max-w-md text-sm leading-relaxed text-muted-fg sm:text-base">
            Five indelible voices. Pick a scene and start talking.
          </p>

          <ul
            ref={castRef}
            className="mt-10 grid gap-x-10 gap-y-12 sm:mt-16 sm:grid-cols-2 sm:gap-y-16 lg:grid-cols-3"
          >
            {CHARACTERS.map((char, i) => (
              <li
                key={char.id}
                className="cast-in"
                style={{ transitionDelay: `${i * 60}ms` }}
              >
                <ClickSpark
                  sparkColor={char.accent}
                  sparkSize={6}
                  sparkRadius={18}
                  sparkCount={8}
                  duration={380}
                  className="h-full"
                >
                  <button
                    type="button"
                    onClick={() => onEnter(char)}
                    className="group relative z-0 flex h-full w-full cursor-pointer flex-col rounded-sm text-left transition duration-200 active:scale-[0.99] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
                  >
                    <div
                      className="cast-card relative mb-5 overflow-hidden rounded-xl border border-white/6 bg-card/50 p-5 shadow-[0_28px_60px_-30px_oklch(0.02_0.02_50)] group-hover:border-accent/30 group-hover:shadow-[0_32px_70px_-28px_var(--cast-glow)]"
                      style={
                        {
                          '--cast-glow': char.glow,
                          filter: 'contrast(1.05) saturate(0.92)',
                        } as CSSProperties
                      }
                    >
                      <span className="cast-shine" aria-hidden />
                      <div
                        className="pointer-events-none absolute inset-0 opacity-50"
                        style={{
                          background: `radial-gradient(ellipse 80% 70% at 20% 0%, ${char.glow}, transparent 60%)`,
                        }}
                        aria-hidden
                      />
                      <div className="relative flex items-center gap-4">
                        <CharacterAvatar character={char} size="lg" />
                        <div className="min-w-0">
                          <span className="block font-serif text-3xl leading-none tracking-[-0.02em] text-foreground transition-transform duration-300 group-hover:translate-x-0.5">
                            {char.name}
                          </span>
                          <span className="mt-2 block text-[0.65rem] uppercase tracking-[0.2em] text-muted-fg">
                            {char.film}
                          </span>
                        </div>
                      </div>
                      <p className="relative mt-5 font-serif text-lg leading-snug italic text-foreground/88">
                        “{char.example}”
                      </p>
                    </div>
                    <span className="text-sm leading-relaxed text-muted-fg">
                      {char.desc}
                    </span>
                    <span className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-accent">
                      Chat with {char.shortName}
                      <ArrowRight
                        className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5"
                        aria-hidden
                      />
                    </span>
                  </button>
                </ClickSpark>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  )
}
