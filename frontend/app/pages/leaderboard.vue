<template>
  <div class="page">
    <div class="header">
      <h1>{{ t('lb.title') }}</h1>
      <p class="sub">{{ t('lb.sub') }}</p>
    </div>

    <div class="panel">
      <div v-if="loading" class="empty">{{ lang === 'fr' ? 'Chargement...' : '加载中...' }}</div>
      <table v-else class="table">
        <thead>
          <tr>
            <th>{{ lang === 'fr' ? 'Rang' : '排名' }}</th>
            <th>{{ lang === 'fr' ? 'Utilisateur' : '用户' }}</th>
            <th>{{ lang === 'fr' ? 'Compte' : '账户' }}</th>
            <th>{{ lang === 'fr' ? 'Valeur' : '总价值' }}</th>
            <th>P&L</th>
            <th>Trades</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in leaderboard" :key="e.rang" :class="{ 'my-row': e.username === myUsername }">
            <td>
              <span class="rang" :class="rankClass(e.rang)">
                {{ e.rang <= 3 ? ['🥇','🥈','🥉'][e.rang-1] : `#${e.rang}` }}
              </span>
            </td>
            <td class="username">{{ e.username }}</td>
            <td class="compte">{{ e.compte_nom }}</td>
            <td class="value">{{ fmtUsd(e.valeur_totale) }}</td>
            <td :class="['pnl', parseFloat(e.pnl_eur) >= 0 ? 'pos' : 'neg']">
              {{ parseFloat(e.pnl_eur) >= 0 ? '+' : '' }}{{ fmtUsd(e.pnl_eur) }}
              <span class="pct">({{ e.pnl_pct >= 0 ? '+' : '' }}{{ e.pnl_pct?.toFixed(2) }}%)</span>
            </td>
            <td class="trades">{{ e.nb_trades }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { useLang } from '../composables/useLang'

const { lang, t } = useLang()
const config      = useRuntimeConfig()
const user        = useState('user')
const leaderboard = ref([])
const loading     = ref(true)
const myUsername  = computed(() => user.value?.username)
const fmtUsd      = v => '$' + parseFloat(v ?? 0).toLocaleString('en-US', { minimumFractionDigits:2, maximumFractionDigits:2 })
const rankClass   = r => r === 1 ? 'gold' : r === 2 ? 'silver' : r === 3 ? 'bronze' : ''

onMounted(async () => {
  leaderboard.value = await $fetch(`${config.public.apiBase}/leaderboard/`)
  loading.value     = false
})
</script>

<style scoped>
.page   { min-height:100vh; background:linear-gradient(160deg,#060810,#0a0f1e); max-width:900px; margin:0 auto; padding:24px; color:#f1f5f9; }
.header { margin-bottom:24px; }
h1 { font-size:22px; font-weight:700; }
.sub { color:#6b7280; font-size:13px; margin-top:4px; }
.panel { background:linear-gradient(135deg,#0d1117,#0f1520); border:1px solid #1e2535; border-radius:16px; padding:20px; }
.empty { color:#4b5563; text-align:center; padding:32px; }
.table { width:100%; border-collapse:collapse; font-size:13px; }
.table th { color:#4b5563; font-size:11px; text-transform:uppercase; letter-spacing:1px; padding:8px 14px; text-align:left; border-bottom:1px solid #1e2535; }
.table td { padding:12px 14px; border-bottom:1px solid #1e2535; }
.table tr:last-child td { border-bottom:none; }
.my-row td { background:rgba(124,58,237,.05); }
.rang   { font-size:16px; font-weight:700; }
.gold   { color:#f59e0b; }
.silver { color:#9ca3af; }
.bronze { color:#92400e; }
.username { font-weight:600; color:#f1f5f9; }
.compte   { color:#6b7280; font-size:12px; }
.value    { font-weight:600; color:#f1f5f9; }
.pos { color:#10b981; font-weight:600; }
.neg { color:#ef4444; font-weight:600; }
.pct    { font-weight:400; font-size:12px; }
.trades { color:#6b7280; }
</style>