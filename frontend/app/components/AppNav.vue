<template>
  <nav class="nav">
    <NuxtLink to="/dashboard" class="logo">
      Crypto<span>Predict</span>
    </NuxtLink>
    <div class="links">
      <NuxtLink to="/dashboard"    class="link">{{ t('nav.dashboard') }}</NuxtLink>
      <NuxtLink to="/portfolio"    class="link">{{ t('nav.portfolio') }}</NuxtLink>
      <NuxtLink v-if="user?.is_staff" to="/admin/training" class="link">{{ t('nav.training') }}</NuxtLink>
      <NuxtLink v-if="user?.is_staff" to="/admin/data"     class="link">{{ t('nav.data') }}</NuxtLink>
      <NuxtLink to="/leaderboard"  class="link">{{ t('nav.leaderboard') }}</NuxtLink>
    </div>
    <div class="user-row">
      <!-- Toggle langue -->
      <ClientOnly>
        <button class="lang-btn" @click="toggle" :title="lang === 'fr' ? '切换到中文' : 'Passer en français'">
          {{ lang === 'fr' ? '🇨🇳 中文' : '🇫🇷 FR' }}
        </button>
      </ClientOnly>
      <span v-if="user" class="username">{{ user.username }}</span>
      <button v-if="user" @click="logout" class="btn-logout">{{ t('nav.logout') }}</button>
      <NuxtLink v-else to="/auth/login" class="btn-login">{{ t('nav.login') }}</NuxtLink>
    </div>
  </nav>
</template>

<script setup>
import { useLang } from '../composables/useLang'

const { lang, toggle, t } = useLang()
const user   = useState('user')
const router = useRouter()

function logout() {
  if (process.client) {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }
  user.value = null
  router.push('/auth/login')
}
</script>

<style scoped>
.nav { display:flex; align-items:center; justify-content:space-between; padding:0 24px; height:56px; background:#0d1117; border-bottom:1px solid #1e2535; position:sticky; top:0; z-index:100; flex-wrap:wrap; gap:8px; }
.logo { font-size:18px; font-weight:700; text-decoration:none; color:#f1f5f9; }
.logo span { color:#7c3aed; }
.links { display:flex; gap:4px; }
.link { color:#6b7280; font-size:13px; font-weight:500; text-decoration:none; padding:6px 12px; border-radius:6px; transition:all .15s; }
.link:hover, .link.router-link-active { color:#f1f5f9; background:rgba(255,255,255,.05); }
.user-row { display:flex; align-items:center; gap:10px; }
.username { color:#6b7280; font-size:13px; }
.lang-btn { background:rgba(255,255,255,.05); border:1px solid #1e2535; color:#9ca3af; border-radius:6px; padding:4px 10px; font-size:12px; cursor:pointer; transition:all .15s; }
.lang-btn:hover { border-color:#7c3aed; color:#a78bfa; }
.btn-logout { background:rgba(239,68,68,.1);   border:1px solid #ef4444; color:#ef4444; border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; }
.btn-login  { background:rgba(124,58,237,.15); border:1px solid #7c3aed; color:#a78bfa; border-radius:6px; padding:5px 12px; font-size:12px; text-decoration:none; }
</style>