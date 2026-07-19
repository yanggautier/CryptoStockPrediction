<template>
  <div class="page">
    <div class="inner">

      <div class="header">
        <div>
          <h1>🗄️ Données d'entraînement</h1>
          <p class="sub">Vue administrateur — données ML disponibles</p>
        </div>
        <button class="btn-refresh" @click="loadData">↻ Rafraîchir</button>
      </div>

      <!-- VUE D'ENSEMBLE -->
      <div class="panel" v-if="overview">
        <h2 class="panel-title">Aperçu général</h2>

        <div class="stats-row">
          <div class="stat-card">
            <p class="stat-label">Données macro</p>
            <p class="stat-value">{{ overview.macro_rows }}</p>
            <p class="stat-desc">jours DXY/SP500/Gold</p>
          </div>
          <div class="stat-card">
            <p class="stat-label">Fear & Greed</p>
            <p class="stat-value">{{ overview.fg_rows }}</p>
            <p class="stat-desc">jours historique</p>
          </div>
          <div class="stat-card">
            <p class="stat-label">Symboles actifs</p>
            <p class="stat-value">{{ overview.symbols?.filter(s => s.rows > 0).length }}/5</p>
            <p class="stat-desc">avec données OHLCV</p>
          </div>
        </div>

        <!-- Tableau symboles -->
        <table class="data-table">
          <thead>
            <tr>
              <th>Symbole</th>
              <th>Lignes OHLCV</th>
              <th>Période</th>
              <th>CSV</th>
              <th>LSTM</th>
              <th>XGBoost</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in overview.symbols" :key="s.symbol">
              <td class="sym-cell">{{ s.symbol.replace('USDT','') }}</td>
              <td>
                <span :class="s.rows > 0 ? 'ok' : 'missing'">
                  {{ s.rows > 0 ? s.rows.toLocaleString() : '—' }}
                </span>
              </td>
              <td class="date-cell">
                <span v-if="s.date_start">
                  {{ s.date_start }} → {{ s.date_end }}
                </span>
                <span v-else class="missing">Aucune donnée</span>
              </td>
              <td><span :class="s.has_csv ? 'badge-ok' : 'badge-missing'">{{ s.has_csv ? '✓' : '✗' }}</span></td>
              <td><span :class="overview.models[s.symbol]?.lstm ? 'badge-ok' : 'badge-missing'">{{ overview.models[s.symbol]?.lstm ? '✓' : '✗' }}</span></td>
              <td><span :class="overview.models[s.symbol]?.xgboost ? 'badge-ok' : 'badge-missing'">{{ overview.models[s.symbol]?.xgboost ? '✓' : '✗' }}</span></td>
              <td>
                <button
                  class="btn-view"
                  :class="{ active: selectedSym === s.symbol }"
                  @click="loadSymbol(s.symbol)"
                >
                  Voir données
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- DONNÉES DÉTAILLÉES PAR SYMBOLE -->
      <div v-if="symbolData" class="panel">
        <div class="panel-head">
          <h2 class="panel-title">{{ selectedSym }} — 100 dernières lignes</h2>
          <span class="sym-badge">{{ symbolData.data?.length }} lignes affichées</span>
        </div>

        <!-- Métriques modèle -->
        <div v-if="symbolData.metrics?.length" class="metrics-section">
          <h3 class="sub-title">Historique des entraînements</h3>
          <table class="data-table sm">
            <thead>
              <tr><th>Type</th><th>RMSE</th><th>MAPE</th><th>Accuracy</th><th>Version</th><th>Date</th></tr>
            </thead>
            <tbody>
              <tr v-for="m in symbolData.metrics" :key="m.created_at">
                <td><span :class="m.model_type === 'lstm' ? 'badge-lstm' : 'badge-xgb'">{{ m.model_type.toUpperCase() }}</span></td>
                <td>{{ m.rmse ? '$' + Number(m.rmse).toLocaleString('en-US', {maximumFractionDigits:0}) : '—' }}</td>
                <td>{{ m.mape ? m.mape.toFixed(2) + '%' : '—' }}</td>
                <td>{{ m.accuracy ? (m.accuracy * 100).toFixed(1) + '%' : '—' }}</td>
                <td>v{{ m.model_version }}</td>
                <td>{{ new Date(m.created_at).toLocaleString('fr-FR', {day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- OHLCV -->
        <h3 class="sub-title" style="margin-top:20px">Données OHLCV</h3>
        <div class="table-wrap">
          <table class="data-table sm">
            <thead>
              <tr>
                <th>Date</th><th>Open</th><th>High</th><th>Low</th>
                <th>Close</th><th>Volume</th><th>RSI</th>
                <th>Returns</th><th>Volatility</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in symbolData.data" :key="row.date">
                <td>{{ row.date }}</td>
                <td>{{ fmtNum(row.open) }}</td>
                <td>{{ fmtNum(row.high) }}</td>
                <td>{{ fmtNum(row.low) }}</td>
                <td class="close-cell">{{ fmtNum(row.close) }}</td>
                <td>{{ row.volume ? Number(row.volume).toLocaleString('en-US', {maximumFractionDigits:0}) : '—' }}</td>
                <td :class="rsiClass(row.rsi)">{{ row.rsi ? row.rsi.toFixed(1) : '—' }}</td>
                <td :class="row.returns >= 0 ? 'pos' : 'neg'">{{ row.returns ? (row.returns * 100).toFixed(2) + '%' : '—' }}</td>
                <td>{{ row.volatility ? (row.volatility * 100).toFixed(2) + '%' : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
definePageMeta({ middleware: 'admin' })

const config   = useRuntimeConfig()
const API      = config.public.apiBase
const getHdrs  = () => ({ Authorization: `Bearer ${process.client ? localStorage.getItem('access_token') ?? '' : ''}` })

const overview    = ref(null)
const symbolData  = ref(null)
const selectedSym = ref(null)
const loading     = ref(false)

const fmtNum  = v => v ? '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits:2, maximumFractionDigits:2 }) : '—'
const rsiClass = v => !v ? '' : v > 70 ? 'rsi-over' : v < 30 ? 'rsi-under' : ''

async function loadData() {
  loading.value = true
  try {
    overview.value = await $fetch(`${API}/admin/data/`, { headers: getHdrs() })
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function loadSymbol(symbol) {
  selectedSym.value = symbol
  symbolData.value  = null
  try {
    symbolData.value = await $fetch(`${API}/admin/data/${symbol}/`, { headers: getHdrs() })
  } catch (e) {
    console.error(e)
  }
}

onMounted(loadData)
</script>

<style scoped>
.page  { min-height:100vh; background:linear-gradient(160deg,#060810,#0a0f1e); color:#f1f5f9; padding:24px; }
.inner { max-width:1200px; margin:0 auto; }

.header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:24px; }
h1 { font-size:22px; font-weight:700; margin:0; }
.sub { color:#6b7280; font-size:13px; margin-top:4px; }
.btn-refresh { background:rgba(124,58,237,.15); border:1px solid #7c3aed; color:#a78bfa; border-radius:8px; padding:8px 16px; font-size:13px; cursor:pointer; }

.panel { background:linear-gradient(135deg,#0d1117,#0f1520); border:1px solid #1e2535; border-radius:16px; padding:24px; margin-bottom:20px; }
.panel-head { display:flex; align-items:center; gap:12px; margin-bottom:16px; }
.panel-title { font-size:16px; font-weight:700; margin:0; }
.sub-title { font-size:13px; font-weight:600; color:#6b7280; margin:0 0 10px; }
.sym-badge { background:#1e2535; color:#6b7280; font-size:11px; border-radius:4px; padding:2px 8px; }

/* Stats */
.stats-row { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:20px; }
.stat-card { background:#060810; border:1px solid #1e2535; border-radius:10px; padding:14px 16px; }
.stat-label{ color:#6b7280; font-size:10px; text-transform:uppercase; letter-spacing:1px; margin:0; }
.stat-value{ color:#a78bfa; font-size:24px; font-weight:700; margin:6px 0 2px; }
.stat-desc { color:#4b5563; font-size:11px; margin:0; }

/* Tables */
.table-wrap { overflow-x:auto; }
.data-table { width:100%; border-collapse:collapse; font-size:12px; }
.data-table th { color:#4b5563; font-size:10px; text-transform:uppercase; letter-spacing:1px; padding:8px 10px; text-align:left; border-bottom:1px solid #1e2535; white-space:nowrap; }
.data-table td { padding:8px 10px; border-bottom:1px solid #1a2030; color:#9ca3af; white-space:nowrap; }
.data-table tr:last-child td { border-bottom:none; }
.data-table tr:hover td { background:rgba(255,255,255,.02); }
.data-table.sm { font-size:11px; }

.sym-cell  { color:#f1f5f9; font-weight:700; }
.date-cell { color:#6b7280; font-size:11px; }
.close-cell{ color:#f1f5f9; font-weight:600; }
.ok      { color:#10b981; font-weight:600; }
.missing { color:#374151; }
.pos { color:#10b981; } .neg { color:#ef4444; }

.badge-ok      { background:rgba(16,185,129,.15); color:#10b981; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:700; }
.badge-missing { background:rgba(239,68,68,.1);   color:#ef4444; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:700; }
.badge-lstm { background:rgba(59,130,246,.15); color:#3b82f6; border-radius:4px; padding:2px 8px; font-size:10px; font-weight:700; }
.badge-xgb  { background:rgba(167,139,250,.15);color:#a78bfa; border-radius:4px; padding:2px 8px; font-size:10px; font-weight:700; }
.metrics-section { background:#060810; border:1px solid #1e2535; border-radius:10px; padding:14px; margin-bottom:4px; }

.rsi-over  { color:#ef4444; font-weight:600; }
.rsi-under { color:#10b981; font-weight:600; }

.btn-view { background:#0d1117; border:1px solid #1e2535; color:#6b7280; border-radius:6px; padding:4px 10px; font-size:11px; cursor:pointer; }
.btn-view.active { border-color:#7c3aed; color:#a78bfa; background:rgba(124,58,237,.1); }
</style>