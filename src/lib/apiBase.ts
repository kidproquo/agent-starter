// Single source of truth for the API base URL the SPA hits.
//
// Vite's `base` option affects asset URLs (with `base: './'` they're emitted
// relative to index.html), but `import.meta.env.BASE_URL` is still a
// compile-time constant. To make ONE build work at any served path (`/`,
// `/app/`, …) we resolve the API URL against `document.baseURI`, which equals
// the actual page URL the browser loaded (e.g. https://host/app/). If a reverse
// proxy mounts the app under a subpath, the frontend container's nginx serves
// the SPA and proxies `/api/` to the FastAPI agent.
//
// VITE_API_BASE still wins if set (e.g. Vite dev pointing at another host).

export function apiBase(): string {
  const override = import.meta.env.VITE_API_BASE as string | undefined
  if (override) return override.replace(/\/$/, '')
  // document.baseURI ends in `/` (it's a directory), so new URL('api', …)
  // joins correctly. We strip the trailing slash since callers append
  // `/chat`.
  return new URL('api', document.baseURI).toString().replace(/\/$/, '')
}
