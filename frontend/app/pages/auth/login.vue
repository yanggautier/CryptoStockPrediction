<template>
  <div class="auth-page">
    <div class="auth-box">
      <h1 class="logo">Crypto<span>Predict</span></h1>
      <p class="sub">Connectez-vous à votre compte</p>
      <div v-if="error" class="error">{{ error }}</div>
      <input v-model="form.username" class="input" placeholder="Nom d'utilisateur" @keyup.enter="submit" />
      <input v-model="form.password" class="input" type="password" placeholder="Mot de passe" @keyup.enter="submit" />
      <button class="btn-primary" :disabled="loading" @click="submit">
        {{ loading ? 'Connexion...' : 'Se connecter' }}
      </button>
      <p class="footer-link">
        Pas encore de compte ?
        <NuxtLink to="/auth/register">S'inscrire</NuxtLink>
      </p>
    </div>
  </div>
</template>

<script setup>
const config  = useRuntimeConfig()
const router  = useRouter()
const user    = useState('user')
const form    = reactive({ username: '', password: '' })
const loading = ref(false)
const error   = ref('')

async function submit() {
  if (!form.username || !form.password) { error.value = 'Remplissez tous les champs'; return }
  loading.value = true; error.value = ''
  try {
    const res = await $fetch(`${config.public.apiBase}/auth/login/`, {
      method: 'POST', body: { username: form.username, password: form.password }
    })
    if (process.client) {
      localStorage.setItem('access_token',  res.access)
      localStorage.setItem('refresh_token', res.refresh)
    }
    const me = await $fetch(`${config.public.apiBase}/auth/me/`, {
      headers: { Authorization: `Bearer ${res.access}` }
    })
    user.value = me
    router.push('/dashboard')
  } catch {
    error.value = 'Identifiants incorrects'
  } finally { loading.value = false }
}
</script>

<style scoped>
.auth-page { min-height:100vh; display:flex; align-items:center; justify-content:center; background:linear-gradient(160deg,#060810,#0a0f1e); padding:24px; }
.auth-box  { background:#0d1117; border:1px solid #1e2535; border-radius:16px; padding:40px; width:100%; max-width:400px; display:flex; flex-direction:column; gap:14px; }
.logo  { font-size:24px; font-weight:700; text-align:center; }
.logo span { color:#7c3aed; }
.sub   { color:#6b7280; font-size:13px; text-align:center; margin-top:-6px; }
.error { background:rgba(239,68,68,.1); border:1px solid #ef4444; color:#ef4444; border-radius:8px; padding:10px 14px; font-size:13px; }
.input { background:#060810; border:1px solid #1e2535; color:#f1f5f9; border-radius:8px; padding:10px 14px; font-size:14px; outline:none; transition:border .15s; }
.input:focus { border-color:#7c3aed; }
.btn-primary { background:linear-gradient(135deg,#7c3aed,#2563eb); border:none; color:white; border-radius:8px; padding:12px; font-size:14px; font-weight:600; cursor:pointer; transition:opacity .15s; }
.btn-primary:hover:not(:disabled) { opacity:.85; }
.btn-primary:disabled { opacity:.5; cursor:wait; }
.footer-link { color:#6b7280; font-size:13px; text-align:center; }
.footer-link a { color:#a78bfa; text-decoration:none; }
</style>