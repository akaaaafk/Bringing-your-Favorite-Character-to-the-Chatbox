/** Base URL for FastAPI. Empty in local dev (Vite proxies /api → :8000). */
export function apiBase(): string {
  return String(import.meta.env.VITE_API_BASE ?? '')
    .trim()
    .replace(/\/$/, '')
}

/** True when the UI talks to a remote API (Vercel + Modal), not local Vite proxy. */
export function isRemoteApi(): boolean {
  return apiBase().length > 0
}

export function apiUrl(path: string): string {
  const base = apiBase()
  const p = path.startsWith('/') ? path : `/${path}`
  return `${base}${p}`
}
