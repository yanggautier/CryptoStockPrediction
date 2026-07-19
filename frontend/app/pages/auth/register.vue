<template>
  <div class="auth-page">
    <div class="auth-box">
      <h1 class="logo">Crypto<span>Predict</span></h1>
      <p class="sub">Créer un compte — 10 000 € virtuels offerts</p>
      <div v-if="error" class="error">{{ error }}</div>
      <div v-if="success" class="success">Compte créé ! Redirection...</div>
      <input v-model="form.username" class="input" placeholder="Nom d'utilisateur" />
      <input v-model="form.password"  class="input" type="password" placeholder="Mot de passe (min. 6 caractères)" />
      <input v-model="form.password2" class="input" type="password" placeholder="Confirmer le mot de passe" @keyup.enter="submit" />
      <div class="info-box">
        🎁 Votre premier compte virtuel sera créé automatiquement avec <strong>10 000 €</strong>
      </div>
      <button class="btn-primary" :disabled="loading" @click="submit">
        {{ loading ? 'Création...' : 'Créer mon compte' }}
      </button>
      <p class="footer-link">
        Déjà un compte ?
        <NuxtLink to="/auth/login">Se connecter</NuxtLink>
      </p>
    </div>
  </div>
</template>

<script setup>
const config  = useRuntimeConfig()
const router  = useRouter()
const user    = useState('user')
const form    = reactive({ username: '', password: '', password2: '' })
const loading = ref(false)
const error   = ref('')
const success = ref(false)

async function submit() {
  error.value = ''
  if (!form.username || !form.password) { error.value = 'Remplissez tous les champs'; return }
  if (form.password.length < 6) { error.value = 'Mot de passe trop court (min. 6 caractères)'; return }
  if (form.password !== form.password2) { error.value = 'Les mots de passe ne correspondent pas'; return }
  loading.value = true
  try {
    const res = await $fetch(`${config.public.apiBase}/auth/register/`, {
      method: 'POST',
      body:   { username: form.username, password: form.password, password2: form.password2 }
    })
    if (process.client) {
      localStorage.setItem('access_token',  res.tokens.access)
      localStorage.setItem('refresh_token', res.tokens.refresh)
    }
    user.value  = res.user
    success.value = true
    setTimeout(() => router.push('/portfolio'), 1500)
  } catch (e) {
    error.value = e?.data?.username?.[0] ?? e?.data?.password?.[0] ?? 'Erreur lors de la création'
  } finally { loading.value = false }
}
</script>

<style scoped>
.auth-page { min-height:100vh; display:flex; align-items:center; justify-content:center; background:linear-gradient(160deg,#060810,#0a0f1e); padding:24px; }
.auth-box  { background:#0d1117; border:1px solid #1e2535; border-radius:16px; padding:40px; width:100%; max-width:400px; display:flex; flex-direction:column; gap:14px; }
.logo  { font-size:24px; font-weight:700; text-align:center; }
.logo span { color:#7c3aed; }
.sub   { color:#6b7280; font-size:13px; text-align:center; margin-top:-6px; }
.error   { background:rgba(239,68,68,.1);   border:1px solid #ef4444; color:#ef4444; border-radius:8px; padding:10px 14px; font-size:13px; }
.success { background:rgba(16,185,129,.1);  border:1px solid #10b981; color:#10b981; border-radius:8px; padding:10px 14px; font-size:13px; }
.input { background:#060810; border:1px solid #1e2535; color:#f1f5f9; border-radius:8px; padding:10px 14px; font-size:14px; outline:none; transition:border .15s; }
.input:focus { border-color:#7c3aed; }
.info-box { background:rgba(124,58,237,.08); border:1px solid rgba(124,58,237,.3); border-radius:8px; padding:12px 14px; font-size:13px; color:#a78bfa; }
.btn-primary { background:linear-gradient(135deg,#7c3aed,#2563eb); border:none; color:white; border-radius:8px; padding:12px; font-size:14px; font-weight:600; cursor:pointer; transition:opacity .15s; }
.btn-primary:hover:not(:disabled) { opacity:.85; }
.btn-primary:disabled { opacity:.5; cursor:wait; }
.footer-link { color:#6b7280; font-size:13px; text-align:center; }
.footer-link a { color:#a78bfa; text-decoration:none; }
</style>