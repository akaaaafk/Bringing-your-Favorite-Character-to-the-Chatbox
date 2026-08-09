import { useMemo, useState } from 'react'
import { Chat } from './components/Chat'
import { Landing } from './components/Landing'
import { CHARACTERS, type Character } from './data/characters'
import { loadChatSession } from './lib/session'

type View = 'landing' | 'chat'

export default function App() {
  const [view, setView] = useState<View>('landing')
  const [character, setCharacter] = useState<Character | undefined>()
  const [landingTick, setLandingTick] = useState(0)

  const resume = useMemo(() => {
    const session = loadChatSession()
    const resumeChar = CHARACTERS.find((c) => c.id === session.lastCharacterId)
    if (!resumeChar) return undefined
    const hasThread = (session.threads[resumeChar.id]?.length ?? 0) > 0
    const hasDraft = !!(session.drafts[resumeChar.id]?.trim())
    if (!hasThread && !hasDraft) return undefined
    return {
      character: resumeChar,
      onResume: () => {
        setCharacter(resumeChar)
        setView('chat')
      },
    }
    // Recompute when returning to landing after a chat session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [landingTick])

  if (view === 'chat') {
    return (
      <Chat
        initialCharacter={character}
        onBack={() => {
          setView('landing')
          setCharacter(undefined)
          setLandingTick((n) => n + 1)
        }}
      />
    )
  }

  return (
    <Landing
      onEnter={(c) => {
        setCharacter(c)
        setView('chat')
      }}
      resume={resume}
    />
  )
}
