export default defineNuxtPlugin(async () => {
  const user   = useState('user')
  const config = useRuntimeConfig()
  const API    = config.public.apiBase

  const accessToken  = localStorage.getItem('access_token')
  const refreshToken = localStorage.getItem('refresh_token')

  if (!accessToken) return

  // Essayer avec le token actuel
  try {
    user.value = await $fetch(`${API}/auth/me/`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    return
  } catch {}

  // Token expiré → tenter le refresh
  if (!refreshToken) {
    localStorage.removeItem('access_token')
    return
  }

  try {
    const res = await $fetch<{ access: string }>(`${API}/auth/token/refresh/`, {
      method: 'POST',
      body:   { refresh: refreshToken },
    })
    localStorage.setItem('access_token', res.access)
    user.value = await $fetch(`${API}/auth/me/`, {
      headers: { Authorization: `Bearer ${res.access}` },
    })
  } catch {
    // Refresh expiré → déconnexion
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    user.value = null
  }
})