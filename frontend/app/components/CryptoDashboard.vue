<template>
  <div class="dashboard">
    <div class="inner">

      <!-- HEADER -->
      <div class="header">
        <div class="sym-tabs">
          <button
            v-for="s in SYMBOLS" :key="s"
            class="tab" :class="{ active: sym === s }"
            @click="sym = s"
          >
            <span class="tab-name">{{ s.replace('USDT','') }}</span>
            <span class="tab-price">{{ fmtUsd(currentPrice(s)) }}</span>
            <span :class="['tab-chg', change(s) >= 0 ? 'pos' : 'neg']">
              {{ change(s) >= 0 ? '▲' : '▼' }} {{ Math.abs(change(s)) }}%
            </span>
          </button>
        </div>
        <div class="header-right">
          <div class="live-row">
            <div class="dot" />
            <span>{{ lastUpdate }}</span>
          </div>
          <button class="refresh-btn" :class="{ spinning: loadingPred }" @click="refreshAll" title="Rafraîchir">↻</button>
          <NuxtLink v-if="user?.is_staff" to="/admin/training" class="train-link">🧠 {{ t('dash.train_btn') }}</NuxtLink>
        </div>
      </div>

      <!-- SECTION 1 : PRIX EN TEMPS RÉEL -->
      <div class="section-header">
        <span class="section-title">📊 {{ t('dash.prices') }}</span>
        <span class="section-sub">{{ t('dash.current') }} · vs hier clôture</span>
      </div>
      <div class="cards">
        <div v-for="s in SYMBOLS" :key="s" :style="cardStyle(s)" class="dir-card" @click="sym = s">
          <div class="card-top">
            <div>
              <p class="card-name">{{ MOCK[s].name }}</p>
              <p class="card-price">{{ fmtUsd(currentPrice(s)) }}</p>
              <p class="card-label">{{ t('dash.current') }}</p>
            </div>
            <div v-if="pct(s) !== null" :style="badgeStyle(s)">
              <div class="badge-icon">{{ isUp(s) ? '↑' : '↓' }}</div>
              <p :class="['badge-pct', isUp(s) ? 'pos' : 'neg']">
                {{ isUp(s) ? '+' : '' }}{{ pct(s) }}%
              </p>
              <p class="badge-label">J+1</p>
            </div>
            <div v-else class="badge-empty">{{ t('dash.no_model') }}</div>
          </div>
          <p v-if="pct(s) !== null" :class="['card-signal', isUp(s) ? 'pos' : 'neg']">
            {{ isUp(s) ? '▲' : '▼' }} LSTM : {{ fmtUsd(nextPred(s)) }}
          </p>
          <div v-if="predData[s]?.ensemble" class="ensemble-row">
            <span :class="['ensemble-badge', strengthClass(predData[s].ensemble.strength)]">
              {{ ensembleIcon(predData[s].ensemble) }} {{ t('strength.' + predData[s].ensemble.strength) }}
            </span>
            <span v-if="predData[s].xgb_signal" class="xgb-proba">
              XGB {{ (predData[s].xgb_signal.probability * 100).toFixed(0) }}%
            </span>
          </div>
          <div v-if="predData[s]?.news_sentiment !== undefined" class="news-sentiment">
            📰 {{ lang === 'fr' ? 'Sentiment news' : 'Sentiments' }} :
            <span :class="predData[sym].news_sentiment > 0.1 ? 'pos' : predData[s].news_sentiment < -0.1 ? 'neg' : ''">
              {{ predData[s].news_sentiment > 0.1 ? '🐂 Haussier' :
                predData[s].news_sentiment < -0.1 ? '🐻 Baissier' : '😐 Neutre' }}
              ({{ predData[s].news_sentiment > 0 ? '+' : '' }}{{ predData[s].news_sentiment.toFixed(3) }})
            </span>
          </div>
        </div>
      </div>

      <!-- SECTION 2 : GRAPHE -->
      <div class="section-header">
        <span class="section-title">📈 {{ MOCK[sym].name }} — {{ t('dash.chart') }}</span>
        <span class="section-sub">{{ pricesData[sym]?.prices?.length ?? 0 }}j {{ t('dash.history') }}<span v-if="loadingPred" class="loading"> · {{ t('dash.loading') }}</span></span>
      </div>
      <div class="panel">
        <!-- Signal ensemble -->
        <div v-if="predData[sym]?.ensemble" class="ensemble-detail">
          <div :class="['ensemble-card', predData[sym].ensemble.tradeable ? 'tradeable' : 'no-trade']">
            <span class="ens-icon">{{ ensembleIcon(predData[sym].ensemble) }}</span>
            <div>
              <p class="ens-title">
                {{ t('dash.signal') }} : <strong>{{ predData[sym].ensemble.signal }}</strong>
                — {{ t('strength.' + predData[sym].ensemble.strength) }}
              </p>
              <p class="ens-sub">
                <span v-if="predData[sym].ensemble.agreement">{{ t('dash.agree') }}</span>
                <span v-else style="color:#f59e0b">{{ t('dash.disagree') }}</span>
                <span v-if="predData[sym].xgb_signal">
                  · {{ t('dash.conf_xgb') }} : {{ t('conf.' + predData[sym].xgb_signal.confidence) }}
                  ({{ (predData[sym].xgb_signal.probability * 100).toFixed(1) }}%)
                </span>
              </p>
            </div>
            <span v-if="!predData[sym].ensemble.tradeable" class="no-trade-badge">{{ t('dash.weak') }}</span>
          </div>
        </div>

        <!-- Légende + période -->
        <div class="chart-controls">
          <div class="legend">
            <div class="leg-item"><div class="leg-line" style="background:#3b82f6" /> {{ t('dash.real') }}</div>
            <div class="leg-item"><div class="leg-line" style="background:#a78bfa" /> LSTM</div>
          </div>
          <div class="period-row">
            <button
              v-for="p in PERIODS" :key="p"
              class="period-btn" :class="{ active: period === p }"
              @click="period = p"
            >{{ t('period.' + p) }}</button>
          </div>
        </div>

        <LineChart v-if="chartData.length" :data="chartData" :split-date="splitDate" />
        <div v-else class="empty-chart">{{ loadingPred ? t('dash.loading') : t('dash.no_data') }}</div>

        <!-- Prévisions 7j -->
        <div v-if="predData[sym]?.forecast?.length" class="forecast-table">
          <p class="forecast-title">{{ t('dash.forecast') }}</p>
          <div class="forecast-row" v-for="(f, i) in predData[sym].forecast" :key="f.date">
            <span class="forecast-day">J+{{ i+1 }}</span>
            <span class="forecast-date">{{ f.date }}</span>
            <span class="forecast-price">{{ fmtUsd(f.price) }}</span>
            <span :class="['forecast-chg', f.price >= (i === 0 ? currentPrice(sym) : predData[sym].forecast[i-1].price) ? 'pos' : 'neg']">
              {{ f.price >= (i === 0 ? currentPrice(sym) : predData[sym].forecast[i-1].price) ? '▲' : '▼' }}
            </span>
          </div>
        </div>
      </div>

      <!-- SECTION 3 : MÉTRIQUES -->
      <div class="section-header">
        <span class="section-title">🎯 {{ t('dash.metrics') }} — {{ sym }}</span>
        <span class="badge-prod">{{ t('dash.production') }}</span>
      </div>
      <div class="panel">
        <div class="metrics-grid">
          <div class="metric-card">
            <p class="m-label">RMSE</p>
            <p class="m-value">{{ predData[sym]?.model_info?.rmse ? fmtUsd(predData[sym].model_info.rmse) : '—' }}</p>
            <p class="m-desc">{{ t('dash.rmse_desc') }}</p>
          </div>
          <div class="metric-card">
            <p class="m-label">MAPE</p>
            <p class="m-value">{{ predData[sym]?.model_info?.mape ? predData[sym].model_info.mape.toFixed(2) + '%' : '—' }}</p>
            <p class="m-desc">{{ t('dash.mape_desc') }}</p>
          </div>
          <div class="metric-card">
            <p class="m-label">XGB</p>
            <p class="m-value">{{ predData[sym]?.xgb_signal ? (predData[sym].xgb_signal.probability * 100).toFixed(1) + '%' : '—' }}</p>
            <p class="m-desc">{{ t('dash.xgb_desc') }}</p>
          </div>
        </div>
        <p class="run-info">run_id : <code>{{ predData[sym]?.model_info?.run_id ?? '—' }}</code></p>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useLang } from '../composables/useLang'

const { t } = useLang()
const config = useRuntimeConfig()
const API    = config.public.apiBase
const user   = useState('user')

const SYMBOLS = ['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT']
const MOCK = {
  BTCUSDT: { name: 'Bitcoin'  },
  ETHUSDT: { name: 'Ethereum' },
  BNBUSDT: { name: 'BNB'      },
  SOLUSDT: { name: 'Solana'   },
  XRPUSDT: { name: 'XRP'      },
}

const sym         = ref('BTCUSDT')
const loadingPred = ref(false)
const pricesData  = ref(Object.fromEntries(SYMBOLS.map(s => [s, null])))
const predData    = ref(Object.fromEntries(SYMBOLS.map(s => [s, null])))
const liveData    = ref(Object.fromEntries(SYMBOLS.map(s => [s, null])))
const period      = ref('3m')
const PERIODS     = ['1w','1m','3m','6m','1y','2y','all']

async function loadSymbol(s) {
  if (s === sym.value) loadingPred.value = true
  try {
    const [prices, pred, live] = await Promise.all([
      $fetch(`${API}/prices/${s}/?period=${period.value}`).catch(() => null),
      $fetch(`${API}/predict/${s}/`).catch(() => null),
      $fetch(`${API}/prices/live/${s}/`).catch(() => null),
    ])
    pricesData.value[s] = prices
    predData.value[s]   = pred
    if (live?.price && pricesData.value[s]?.prices?.length) {
      const arr = pricesData.value[s].prices
      arr[arr.length - 1] = { ...arr[arr.length - 1], price: live.price }
    }
    liveData.value[s] = live
    lastUpdate.value  = new Date().toLocaleTimeString('fr-FR', { hour:'2-digit', minute:'2-digit' })
  } finally {
    if (s === sym.value) loadingPred.value = false
  }
}

onMounted(async () => {
  await loadSymbol(sym.value)
  for (const s of SYMBOLS.filter(s => s !== sym.value)) loadSymbol(s)
  setInterval(() => loadSymbol(sym.value), 3_600_000)
})

watch(sym,    s => { if (!predData.value[s]) loadSymbol(s) })
watch(period, () => loadSymbol(sym.value))

const chartData = computed(() => {
  const history  = pricesData.value[sym.value]?.prices  ?? []
  const forecast = predData.value[sym.value]?.forecast  ?? []
  if (!history.length) return []
  return [...history, ...forecast.map(f => ({ date: f.date, forecast: f.price }))]
})

const splitDate    = computed(() => { const h = pricesData.value[sym.value]?.prices ?? []; return h[h.length - 1]?.date })
const currentPrice = s => liveData.value[s]?.price ?? pricesData.value[s]?.prices?.slice(-1)[0]?.price ?? 0
const nextPred     = s => predData.value[s]?.forecast?.[0]?.price ?? 0
const isUp         = s => nextPred(s) > 0 && nextPred(s) >= currentPrice(s)
const pct          = s => { const cur = currentPrice(s), pred = nextPred(s); if (!cur || !pred) return null; return (((pred - cur) / cur) * 100).toFixed(2) }
const change       = s => liveData.value[s]?.change ?? 0
const fmtUsd       = v => { if (!v) return '—'; return '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits:2, maximumFractionDigits:2 }) }

async function refreshAll() {
  predData.value[sym.value]   = null
  pricesData.value[sym.value] = null
  liveData.value[sym.value]   = null
  await loadSymbol(sym.value)
}

const cardStyle   = s => ({ background:'linear-gradient(135deg,#0d1117,#111827)', border:`1px solid ${isUp(s)?'#064e3b':'#4c0519'}`, borderRadius:'12px', padding:'16px 20px', cursor:'pointer', transition:'transform .15s' })
const badgeStyle  = s => ({ background: isUp(s)?'rgba(16,185,129,.15)':'rgba(239,68,68,.15)', borderRadius:'10px', padding:'10px 14px', textAlign:'center' })
const strengthClass = strength => ({'FORT':'ens-fort','MOYEN':'ens-moyen','CONTRADICTOIRE':'ens-contra'}[strength]??'')
const ensembleIcon  = ens => ens.strength === 'CONTRADICTOIRE' ? '⚡' : ens.signal === 'HAUSSE' ? '🟢' : '🔴'

const lastUpdate = ref('')
onMounted(() => {
  lastUpdate.value = new Date().toLocaleTimeString('fr-FR', { hour:'2-digit', minute:'2-digit' })
})
</script>

<style scoped>
.dashboard { min-height:100vh; background:linear-gradient(160deg,#060810,#0a0f1e); color:#f1f5f9; padding:24px; }
.inner { max-width:1200px; margin:0 auto; }
.header { display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-wrap:wrap; gap:12px; }
.sym-tabs { display:flex; gap:8px; flex-wrap:wrap; }
.tab { background:#0d1117; border:1px solid #1e2535; border-radius:10px; padding:10px 16px; cursor:pointer; display:flex; flex-direction:column; align-items:flex-start; gap:2px; min-width:100px; transition:all .15s; }
.tab.active { background:linear-gradient(135deg,rgba(124,58,237,.25),rgba(37,99,235,.15)); border-color:#7c3aed; }
.tab-name { color:#f1f5f9; font-size:13px; font-weight:600; }
.tab-price { color:#6b7280; font-size:11px; white-space:nowrap; }
.tab-chg { font-size:11px; font-weight:600; }
.header-right { display:flex; align-items:center; gap:12px; }
.live-row { display:flex; align-items:center; gap:6px; color:#6b7280; font-size:12px; }
.dot { width:7px; height:7px; border-radius:50%; background:#10b981; animation:pulse 2s infinite; }
.train-link { display:flex; align-items:center; gap:6px; background:rgba(124,58,237,.15); border:1px solid #7c3aed; color:#a78bfa; border-radius:8px; padding:8px 14px; font-size:13px; font-weight:600; text-decoration:none; }
.refresh-btn { background:rgba(255,255,255,.05); border:1px solid #1e2535; color:#6b7280; border-radius:8px; width:34px; height:34px; font-size:16px; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:all .2s; }
.refresh-btn:hover { color:#f1f5f9; border-color:#374151; }
.refresh-btn.spinning { animation:spin 1s linear infinite; color:#7c3aed; }
/* Section headers */
.section-header { display:flex; align-items:center; gap:10px; margin:24px 0 12px; }
.section-title { font-size:15px; font-weight:700; color:#f1f5f9; }
.section-sub { color:#4b5563; font-size:12px; }
/* Cards */
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; margin-bottom:8px; }
.dir-card:hover { transform:translateY(-2px); }
.card-top { display:flex; justify-content:space-between; }
.card-name { color:#6b7280; font-size:11px; text-transform:uppercase; letter-spacing:1px; margin:0; }
.card-price { color:#f1f5f9; font-size:18px; font-weight:700; margin:6px 0 2px; white-space:nowrap; }
.card-label { color:#6b7280; font-size:11px; margin:0; }
.badge-icon { font-size:20px; } .badge-pct { font-size:13px; font-weight:700; margin:4px 0 0; } .badge-label { color:#6b7280; font-size:10px; margin:0; }
.badge-empty { color:#374151; font-size:10px; text-align:center; padding:6px 8px; border:1px solid #1e2535; border-radius:8px; line-height:1.4; white-space:pre-line; }
.card-signal { font-size:12px; margin-top:8px; }
.ensemble-row { display:flex; align-items:center; gap:6px; margin-top:6px; flex-wrap:wrap; }
.ensemble-badge { font-size:10px; font-weight:700; border-radius:4px; padding:2px 7px; }
.ens-fort   { background:rgba(16,185,129,.15); color:#10b981; border:1px solid #10b981; }
.ens-moyen  { background:rgba(245,158,11,.15); color:#f59e0b; border:1px solid #f59e0b; }
.ens-contra { background:rgba(239,68,68,.15);  color:#ef4444; border:1px solid #ef4444; }
.xgb-proba  { color:#4b5563; font-size:10px; }
/* Panel */
.panel { background:linear-gradient(135deg,#0d1117,#0f1520); border:1px solid #1e2535; border-radius:16px; padding:24px; margin-bottom:8px; }
.chart-controls { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:10px; }
.legend { display:flex; gap:16px; }
.leg-item { display:flex; align-items:center; gap:6px; color:#6b7280; font-size:12px; }
.leg-line { width:20px; height:2px; }
.period-row { display:flex; gap:6px; flex-wrap:wrap; }
.period-btn { background:#0d1117; border:1px solid #1e2535; color:#6b7280; border-radius:6px; padding:4px 10px; font-size:11px; font-weight:600; cursor:pointer; transition:all .15s; }
.period-btn.active { background:rgba(124,58,237,.15); border-color:#7c3aed; color:#a78bfa; }
.empty-chart { height:300px; display:flex; align-items:center; justify-content:center; color:#4b5563; font-size:14px; }
/* Ensemble */
.ensemble-detail { margin-bottom:16px; }
.ensemble-card { display:flex; align-items:center; gap:12px; padding:12px 16px; border-radius:10px; border:1px solid #1e2535; flex-wrap:wrap; }
.ensemble-card.tradeable { border-color:#10b981; background:rgba(16,185,129,.05); }
.ensemble-card.no-trade  { border-color:#f59e0b; background:rgba(245,158,11,.05); }
.ens-icon { font-size:20px; } .ens-title { font-size:13px; font-weight:600; margin:0; color:#f1f5f9; } .ens-sub { font-size:12px; color:#6b7280; margin:2px 0 0; }
.no-trade-badge { margin-left:auto; background:rgba(245,158,11,.15); color:#f59e0b; font-size:11px; border-radius:5px; padding:2px 8px; border:1px solid #f59e0b; }
/* Forecast */
.forecast-table { margin-top:16px; border-top:1px solid #1e2535; padding-top:16px; }
.forecast-title { color:#6b7280; font-size:11px; text-transform:uppercase; letter-spacing:1px; margin:0 0 10px; }
.forecast-row { display:flex; align-items:center; gap:16px; padding:6px 0; border-bottom:1px solid #1a2030; }
.forecast-row:last-child { border-bottom:none; }
.forecast-day { color:#4b5563; font-size:12px; font-weight:600; min-width:30px; } .forecast-date { color:#374151; font-size:11px; flex:1; } .forecast-price { color:#f1f5f9; font-weight:600; font-size:13px; } .forecast-chg { font-size:12px; min-width:16px; }
/* Metrics */
.badge-prod { background:rgba(124,58,237,.15); border:1px solid #7c3aed; color:#a78bfa; font-size:10px; border-radius:5px; padding:2px 8px; }
.metrics-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; }
.metric-card { background:#0d1117; border:1px solid #1e2535; border-radius:10px; padding:14px 16px; }
.m-label { color:#6b7280; font-size:10px; text-transform:uppercase; letter-spacing:1px; margin:0; } .m-value { color:#a78bfa; font-size:20px; font-weight:700; margin:6px 0 2px; } .m-desc { color:#4b5563; font-size:11px; margin:0; }
.run-info { color:#374151; font-size:11px; margin-top:14px; } .run-info code { color:#4b5563; }
.loading { color:#f59e0b; font-size:11px; animation:pulse 1.5s infinite; }
.pos { color:#10b981; } .neg { color:#ef4444; }
@keyframes spin  { from{transform:rotate(0)}   to{transform:rotate(360deg)} }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
</style>