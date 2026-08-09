# Shape brief — Avatar presence + tap-to-talk voice

Confirmed answers: **1B · 2A (toggle tap, not hold) · 3A**

## 1. Job and audience

Course demo visitors pick a movie persona and talk with it. Mode on chat: **Operate** (complete a conversation). Landing stays Persuade. Success: they hear and see a character respond without needing paid APIs.

## 2. Outcome and proof

- Primary action: tap mic → speak → tap stop → get spoken + written reply in character
- Proof of product: Best-of-N persona reply still drives the words; voice is I/O only
- Product-specific truth: five Cornell-trained styles, not a generic Siri

## 3. Selected direction

- **Avatars (1B):** circular/portrait presence per character on rail + conversation header; while assistant TTS plays, subtle mouth/energy animation (CSS/SVG or lightweight Lottie-like loop)—not full video digital humans
- **Voice (2A + toggle):** Web Speech API `SpeechRecognition` (tap start / tap stop) → text into existing `/api/chat` → `speechSynthesis` for reply; demo text path unchanged if speech unsupported
- **Reliability (3A):** no ElevenLabs/HeyGen required; optional upgrade hooks later
- Focal moment: mic armed state + avatar “speaking” while reply is voiced
- Implementation consequence: extend `characters.ts` with avatar asset URLs; Chat gains mic control + speak-on-reply; Landing cast may show avatars

## 4. Scope and boundaries

**In**

- Static/stylized avatars + speaking feedback
- Tap-toggle recording → STT → chat → TTS
- Permission / unsupported / empty-transcript error states
- Keep typed input and send

**Out (anti-goals)**

- Hold-to-talk
- Always-on wake word / continuous Siri listening
- Photoreal talking-head video APIs
- Replacing LoRA/classifier with a cloud voice agent

**Untouched:** training pipeline, Best-of-N core, projection-room visual world tokens

## 5. States and ranges

- Mic: idle → recording → processing → error (denied / no speech / unsupported)
- Avatar: idle / listening (user recording) / speaking (TTS)
- Content: 5 characters; replies short chat turns; demo mode still works
- Languages: browser-default recognition/TTS (typically en-US for this corpus)

## 6. Interaction and layout

- Header: large avatar + name/film; rail: small avatar per character
- Composer: text field + **mic toggle** + send; mic shows clear recording affordance (pulse ring)
- Second tap ends recording and starts recognition; transcript fills input or auto-sends (prefer auto-send after successful transcript for Siri-like flow, with text still editable if recognition fails mid-way—**recommend auto-send on success**)
- Assistant bubble appears; TTS starts; avatar enters speaking state until utterance ends
- Mobile: mic control ≥44px touch target; rail stays horizontal scroll

## 7. Constraints and open decisions for builder

- Prefer `/public/avatars/{id}.svg` or PNG placeholders if no photos supplied; label synthetic in code comments only, not in UI chrome
- Chrome/Edge best for Web Speech; Safari partial—detect and show “Voice unavailable, type instead”
- Do not invent API keys; no new paid deps for v1
- Open for confirmation: **auto-send after STT** vs paste into input and wait for Send—brief recommends **auto-send on successful transcript**
