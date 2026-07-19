<template>
  <div class="training-page">
    <div class="inner">  
      <!-- HEADER -->
      <div class="header">
        <div class="logo-row">
          <div class="logo-icon">⬡</div>
          <div>
            <h1>Crypto<span style="color:#7c3aed">Predict</span></h1>
            <p class="sub">Centre d'entraînement ML</p>
          </div>
        </div>
      </div>

      <!-- SÉLECTEUR SYMBOLE -->
      <div class="panel">
        <h2 class="panel-title">Lancer un entraînement</h2>
        <div class="symbol-row">
          <button
            v-for="s in SYMBOLS" :key="s"
            class="sym-btn" :class="{ active: selected === s }"
            @click="selected = s"
          >
            {{ s.replace('USDT','') }}
          </button>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <button class="train-btn" :disabled="isRunning" @click="startTraining">
            <span v-if="isRunning" class="spin">⟳</span>
            <span v-else>🧠</span>
            {{ isRunning ? 'Entraînement en cours...' : 'Lancer l\'entraînement' }}
          </button>
          <button v-if="isRunning" class="btn-cancel-job" @click="cancelJob">
            ✕ Annuler
          </button>
        </div>
      </div>

      <!-- PROGRESSION -->
      <div v-if="job" class="panel">
        <div class="job-header">
          <div>
            <h2 class="panel-title">{{ job.symbol }} — {{ job.current_step }}</h2>
            <p class="sub">Démarré {{ formatDate(job.started_at) }}</p>
          </div>
          <span class="badge" :class="statusClass">{{ statusLabel }}</span>
        </div>

        <div class="progress-track">
          <div class="progress-bar" :style="{ width: job.progress + '%' }" />
        </div>
        <div class="progress-labels">
          <span :class="{ done: job.progress >= 20  }">Données</span>
          <span :class="{ done: job.progress >= 70  }">LSTM</span>
          <span :class="{ done: job.progress >= 92  }">XGBoost</span>
          <span :class="{ done: job.progress >= 100 }">Terminé</span>
        </div>

        <div v-if="job.status === 'SUCCESS'" class="metrics-row">
          <div class="metric-card">
            <p class="m-label">LSTM RMSE</p>
            <p class="m-value">${{ Number(job.lstm_rmse).toLocaleString('fr-FR', {maximumFractionDigits:0}) }}</p>
          </div>
          <div class="metric-card">
            <p class="m-label">LSTM MAPE</p>
            <p class="m-value">{{ job.lstm_mape?.toFixed(2) }}%</p>
          </div>
          <div class="metric-card">
            <p class="m-label">XGBoost Accuracy</p>
            <p class="m-value">{{ job.xgb_accuracy ? (job.xgb_accuracy*100).toFixed(1)+'%' : '—' }}</p>
          </div>
          <div class="metric-card">
            <p class="m-label">MLflow run_id</p>
            <p class="m-value" style="font-size:11px;color:#6b7280">{{ job.run_id?.slice(0,12) }}...</p>
          </div>
        </div>

        <div class="log-box" ref="logBox">
          <p v-for="(line, i) in logLines" :key="i" class="log-line">{{ line }}</p>
          <span v-if="isRunning" class="cursor">▌</span>
        </div>
      </div>

      <!-- HISTORIQUE PAR SYMBOLE -->
      <div v-if="history.length" class="panel">
        <div class="history-header">
          <h2 class="panel-title" style="margin:0">Historique</h2>
          <span class="total-badge">{{ history.length }} run{{ history.length > 1 ? 's' : '' }}</span>
        </div>

        <!-- Onglets -->
        <div class="tabs">
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'ALL' }"
            @click="activeTab = 'ALL'"
          >
            Tous
            <span class="tab-count">{{ history.length }}</span>
          </button>
          <button
            v-for="s in symbolsWithData"
            :key="s"
            class="tab-btn"
            :class="{ active: activeTab === s }"
            @click="activeTab = s"
          >
            {{ s.replace('USDT','') }}
            <span class="tab-count">{{ history.filter(j => j.symbol === s).length }}</span>
          </button>
        </div>

        <!-- Résumé stats (si filtre actif sur une crypto) -->
        <div v-if="activeTab !== 'ALL' && summaryStats.success > 0" class="summary-row">
          <div class="summary-card">
            <p class="sum-label">Runs</p>
            <p class="sum-val">{{ summaryStats.total }}</p>
            <p class="sum-sub">{{ summaryStats.success }} réussi{{ summaryStats.success > 1 ? 's' : '' }}</p>
          </div>
          <div class="summary-card">
            <p class="sum-label">Meilleur RMSE</p>
            <p class="sum-val">{{ summaryStats.bestRmseFormatted }}</p>
            <p class="sum-sub">LSTM</p>
          </div>
          <div class="summary-card">
            <p class="sum-label">XGB Acc. moy.</p>
            <p class="sum-val">{{ summaryStats.avgAcc !== null ? (summaryStats.avgAcc * 100).toFixed(1) + '%' : '—' }}</p>
            <p class="sum-sub">moyenne</p>
          </div>
          <div class="summary-card">
            <p class="sum-label">Taux réussite</p>
            <p class="sum-val">{{ summaryStats.total > 0 ? Math.round(summaryStats.success / summaryStats.total * 100) + '%' : '—' }}</p>
            <p class="sum-sub">success rate</p>
          </div>
        </div>

        <!-- Tableau -->
        <div v-if="filteredHistory.length === 0" class="empty-state">
          Aucun entraînement pour ce symbole.
        </div>
        <table v-else class="hist-table">
          <thead>
            <tr>
              <th v-if="activeTab === 'ALL'" style="width:80px">Symbole</th>
              <th>Statut</th>
              <th>RMSE</th>
              <th>MAPE</th>
              <th>XGB Acc.</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="j in filteredHistory" :key="j.id">
              <td v-if="activeTab === 'ALL'">
                <span class="sym-pill">{{ j.symbol.replace('USDT','') }}</span>
              </td>
              <td><span class="badge" :class="badgeClass(j.status)">{{ badgeLabel(j.status) }}</span></td>
              <td class="num">{{ j.lstm_rmse ? '$' + Number(j.lstm_rmse).toLocaleString('fr-FR', {maximumFractionDigits:0}) : '—' }}</td>
              <td class="num">{{ j.lstm_mape ? j.lstm_mape.toFixed(2) + '%' : '—' }}</td>
              <td class="num">{{ j.xgb_accuracy ? (j.xgb_accuracy * 100).toFixed(1) + '%' : '—' }}</td>
              <td class="num">{{ formatDate(j.started_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

    </div>
  </div>
</template>

<script setup>
definePageMeta({ middleware: 'admin' })
import { ref, computed, watch, nextTick, onUnmounted, onMounted } from 'vue'

const config  = useRuntimeConfig()
const API     = config.public.apiBase
const token   = computed(() => process.client ? localStorage.getItem('access_token') ?? '' : '')
const headers = computed(() => ({ Authorization: `Bearer ${token.value}` }))

const SYMBOLS  = ['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT']
const selected = ref('BTCUSDT')
const job      = ref(null)
const history  = ref([])
const logBox   = ref(null)
const activeTab = ref('ALL')
let pollTimer  = null

// ── Symboles ayant des runs dans l'historique (ordre du tableau SYMBOLS)
const symbolsWithData = computed(() =>
  SYMBOLS.filter(s => history.value.some(j => j.symbol === s))
)

// ── Historique filtré par onglet (du plus récent au plus ancien)
const filteredHistory = computed(() => {
  const list = activeTab.value === 'ALL'
    ? history.value
    : history.value.filter(j => j.symbol === activeTab.value)
  return [...list]
})

// ── Stats de résumé pour l'onglet courant
const summaryStats = computed(() => {
  const jobs = activeTab.value === 'ALL' ? history.value : history.value.filter(j => j.symbol === activeTab.value)
  const done = jobs.filter(j => j.status === 'SUCCESS')
  const bestRmse = done.length ? Math.min(...done.map(j => j.lstm_rmse)) : null
  const sym = activeTab.value
  let bestRmseFormatted = '—'
  if (bestRmse !== null) {
    if (sym === 'XRPUSDT') bestRmseFormatted = '$' + Number(bestRmse).toFixed(4)
    else if (sym === 'SOLUSDT') bestRmseFormatted = '$' + Number(bestRmse).toFixed(2)
    else bestRmseFormatted = '$' + Number(bestRmse).toLocaleString('fr-FR', { maximumFractionDigits: 0 })
  }
  return {
    total: jobs.length,
    success: done.length,
    bestRmseFormatted,
    avgAcc: done.length ? done.reduce((a, j) => a + (j.xgb_accuracy || 0), 0) / done.length : null,
  }
})

// ── Statut job courant
const isRunning   = computed(() => job.value?.status === 'RUNNING' || job.value?.status === 'PENDING')
const statusLabel = computed(() => ({ PENDING:'En attente', RUNNING:'En cours', SUCCESS:'Terminé ✓', FAILURE:'Erreur' }[job.value?.status] ?? ''))
const statusClass = computed(() => ({ PENDING:'badge-yellow', RUNNING:'badge-blue', SUCCESS:'badge-green', FAILURE:'badge-red' }[job.value?.status]))

const badgeClass = (s) => ({ PENDING:'badge-yellow', RUNNING:'badge-blue', SUCCESS:'badge-green', FAILURE:'badge-red' }[s])
const badgeLabel = (s) => ({ PENDING:'En attente', RUNNING:'En cours', SUCCESS:'Terminé', FAILURE:'Erreur' }[s] || s)

const logLines = computed(() => (job.value?.log || '').split('\n').filter(Boolean))

// ── Persistence
const saveActiveJob  = (id) => { if (process.client) localStorage.setItem('active_training_job', String(id)) }
const clearActiveJob = ()   => { if (process.client) localStorage.removeItem('active_training_job') }

// ── Polling
const startPolling = (jobId) => {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const updated = await $fetch(`${API}/train/${jobId}/`)
      job.value = updated
      await nextTick()
      if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
      if (!isRunning.value) { stopPolling(); await fetchHistory() }
    } catch (e) { console.warn('Polling error:', e) }
  }, 2000)
}
const stopPolling = () => { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }

// ── Actions
const startTraining = async () => {
  const tok = localStorage.getItem('access_token')
  try {
    const res = await $fetch(`${API}/train/`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' },
      body: { symbol: selected.value },
    })
    job.value = res.job
    saveActiveJob(res.job.id)
    startPolling(res.job.id)
    await fetchHistory()
  } catch (e) { console.error('Erreur:', e) }
}

const fetchHistory = async () => {
  try {
    history.value = await $fetch(`${API}/train/history/`, { headers: headers.value })
  } catch { history.value = [] }
}

const cancelJob = async () => {
  stopPolling()
  clearActiveJob()
  if (job.value) job.value = { ...job.value, status: 'FAILURE', current_step: 'Annulé' }
  try { await $fetch(`${API}/train/${job.value?.id}/cancel/`, { method: 'POST' }) } catch {}
  job.value = null
  await fetchHistory()
}

const formatDate = (dt) => {
  if (!dt) return ''
  return new Date(dt).toLocaleString('fr-FR', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' })
}

// ── Lifecycle
onMounted(async () => {
  await fetchHistory()
  const savedJobId = process.client ? localStorage.getItem('active_training_job') : null
  if (savedJobId) {
    try {
      const restored = await $fetch(`${API}/train/${savedJobId}/`)
      job.value = restored
      if (restored.status === 'RUNNING' || restored.status === 'PENDING') startPolling(Number(savedJobId))
      else clearActiveJob()
    } catch { clearActiveJob() }
  }
})

watch(() => job.value?.status, (status) => {
  if (status === 'SUCCESS' || status === 'FAILURE') { clearActiveJob(); stopPolling() }
})

onUnmounted(stopPolling)
</script>

<style scoped>
.training-page { min-height:100vh; background:linear-gradient(160deg,#060810,#0a0f1e); color:#f1f5f9; padding:24px; font-family:'Inter',system-ui,sans-serif; }
.inner { max-width:900px; margin:0 auto; }
.header { display:flex; align-items:center; margin-bottom:28px; }
.logo-row { display:flex; align-items:center; gap:12px; }
.logo-icon { width:36px; height:36px; border-radius:10px; background:linear-gradient(135deg,#7c3aed,#2563eb); display:flex; align-items:center; justify-content:center; }
h1 { font-size:20px; font-weight:700; margin:0; }
.sub { color:#4b5563; font-size:11px; margin:0; }

.panel { background:linear-gradient(135deg,#0d1117,#0f1520); border:1px solid #1e2535; border-radius:16px; padding:24px; margin-bottom:20px; max-width:900px; }
.panel-title { font-size:15px; font-weight:700; margin:0 0 16px; }

/* Lancer */
.symbol-row { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px; }
.sym-btn { background:#0d1117; border:1px solid #1e2535; color:#f1f5f9; border-radius:8px; padding:8px 16px; cursor:pointer; font-weight:600; transition:all .15s; }
.sym-btn.active { background:rgba(124,58,237,.2); border-color:#7c3aed; color:#a78bfa; }
.train-btn { display:flex; align-items:center; gap:8px; background:rgba(124,58,237,.15); border:1px solid #7c3aed; color:#a78bfa; border-radius:8px; padding:10px 20px; font-size:14px; font-weight:600; cursor:pointer; transition:all .15s; }
.train-btn:disabled { opacity:.5; cursor:wait; }
.btn-cancel-job { background:rgba(239,68,68,.1); border:1px solid #ef4444; color:#ef4444; border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; }
.spin { display:inline-block; animation:spin 1s linear infinite; }

/* Progression */
.job-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; }
.progress-track { background:#1e2535; border-radius:99px; height:8px; overflow:hidden; margin-bottom:8px; }
.progress-bar { height:100%; background:linear-gradient(90deg,#7c3aed,#2563eb); border-radius:99px; transition:width .5s ease; }
.progress-labels { display:flex; justify-content:space-between; font-size:11px; color:#374151; margin-bottom:20px; }
.progress-labels span.done { color:#10b981; }
.metrics-row { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:16px; }
.metric-card { background:#0d1117; border:1px solid #1e2535; border-radius:10px; padding:12px; }
.m-label { color:#6b7280; font-size:10px; text-transform:uppercase; letter-spacing:1px; margin:0; }
.m-value { color:#a78bfa; font-size:18px; font-weight:700; margin:4px 0 0; }
.log-box { background:#060810; border:1px solid #1e2535; border-radius:8px; padding:12px 16px; height:200px; overflow-y:auto; font-family:monospace; font-size:12px; }
.log-line { color:#6b7280; margin:2px 0; }
.log-line:last-child { color:#a78bfa; }
.cursor { color:#7c3aed; animation:blink .8s step-end infinite; }

/* Historique */
.history-header { display:flex; align-items:center; gap:10px; margin-bottom:16px; }
.total-badge { font-size:11px; background:rgba(124,58,237,.15); border:1px solid rgba(124,58,237,.3); color:#a78bfa; border-radius:99px; padding:2px 10px; }

/* Onglets */
.tabs { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:16px; border-bottom:1px solid #1e2535; padding-bottom:12px; }
.tab-btn { background:transparent; border:1px solid #1e2535; color:#6b7280; border-radius:8px; padding:5px 14px; font-size:13px; font-weight:500; cursor:pointer; transition:all .15s; display:flex; align-items:center; gap:6px; }
.tab-btn:hover { border-color:#374151; color:#9ca3af; }
.tab-btn.active { background:rgba(124,58,237,.15); border-color:#7c3aed; color:#a78bfa; }
.tab-count { font-size:11px; background:rgba(255,255,255,.07); border-radius:99px; padding:1px 7px; color:inherit; }
.tab-btn.active .tab-count { background:rgba(124,58,237,.25); }

/* Résumé stats */
.summary-row { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:16px; }
.summary-card { background:#0d1117; border:1px solid #1e2535; border-radius:10px; padding:12px 14px; }
.sum-label { color:#6b7280; font-size:10px; text-transform:uppercase; letter-spacing:.08em; margin:0 0 4px; }
.sum-val { color:#a78bfa; font-size:20px; font-weight:700; margin:0 0 2px; }
.sum-sub { color:#4b5563; font-size:11px; margin:0; }

/* Tableau */
.empty-state { color:#4b5563; font-size:13px; padding:24px 0; text-align:center; }
.hist-table { width:100%; border-collapse:collapse; font-size:13px; }
.hist-table th { color:#4b5563; font-size:11px; text-transform:uppercase; letter-spacing:.08em; padding:8px 12px; text-align:left; border-bottom:1px solid #1e2535; }
.hist-table td { padding:10px 12px; border-bottom:1px solid #1e2535; }
.hist-table tr:last-child td { border-bottom:none; }
.hist-table tr:hover td { background:rgba(255,255,255,.02); }
.num { color:#9ca3af; font-variant-numeric:tabular-nums; }
.sym-pill { display:inline-block; background:rgba(124,58,237,.1); border:1px solid rgba(124,58,237,.25); color:#a78bfa; border-radius:6px; padding:2px 8px; font-size:12px; font-weight:600; }

/* Badges */
.badge { font-size:11px; border-radius:5px; padding:3px 10px; font-weight:600; }
.badge-yellow { background:rgba(245,158,11,.15); color:#f59e0b; border:1px solid #f59e0b; }
.badge-blue   { background:rgba(59,130,246,.15);  color:#3b82f6;  border:1px solid #3b82f6; }
.badge-green  { background:rgba(16,185,129,.15);  color:#10b981;  border:1px solid #10b981; }
.badge-red    { background:rgba(239,68,68,.15);   color:#ef4444;  border:1px solid #ef4444; }

@keyframes spin  { from{transform:rotate(0)}  to{transform:rotate(360deg)} }
@keyframes blink { 50%{opacity:0} }
</style>