<template>
  <div class="page">

    <!-- COMPTES -->
    <div class="section">
      <div class="section-head">
        <h2>{{ t('port.accounts') }}</h2>
        <button v-if="accounts.length < 3" class="btn-add" @click="showCreate = true">
          {{ t('port.new') }}
        </button>
      </div>

      <div v-if="showCreate" class="create-box">
        <input v-model="newName" class="input"
          :placeholder="lang === 'fr' ? 'Nom du compte (ex: Stratégie LSTM)' : '账户名称 (如: LSTM 策略)'"
          @keyup.enter="createAccount" />
        <button class="btn-primary" @click="createAccount">{{ lang === 'fr' ? 'Créer' : '创建' }}</button>
        <button class="btn-cancel" @click="showCreate=false; newName=''">{{ lang === 'fr' ? 'Annuler' : '取消' }}</button>
      </div>

      <div class="accounts-tabs">
        <div v-for="acc in accounts" :key="acc.id"
          class="account-tab" :class="{ active: activeAcc?.id === acc.id }"
          @click="selectAcc(acc)">
          <div class="tab-top">
            <span class="tab-name">{{ acc.nom }}</span>
            <span class="tab-badge">{{ acc.nb_trades }} trades</span>
          </div>
          <p class="tab-value">{{ fmtUsd(acc.valeur_totale) }}</p>
          <p :class="['tab-pnl', parseFloat(acc.pnl_total) >= 0 ? 'pos' : 'neg']">
            {{ parseFloat(acc.pnl_total) >= 0 ? '+' : '' }}{{ fmtUsd(acc.pnl_total) }}
            ({{ acc.pnl_pct >= 0 ? '+' : '' }}{{ acc.pnl_pct != null ? acc.pnl_pct.toFixed(2) : '0.00' }}%)
          </p>
          <p class="tab-solde">{{ t('port.available') }} : {{ fmtUsd(acc.solde) }}</p>
        </div>
      </div>
    </div>

    <!-- RÉSUMÉ -->
    <div v-if="activeAcc" class="summary-bar">
      <div class="sum-item">
        <p class="sum-label">{{ lang === 'fr' ? 'Valeur totale' : '总价值' }}</p>
        <p class="sum-val">{{ fmtUsd(activeAcc.valeur_totale) }}</p>
      </div>
      <div class="sum-item">
        <p class="sum-label">{{ lang === 'fr' ? 'Solde disponible' : '可用余额' }}</p>
        <p class="sum-val">{{ fmtUsd(activeAcc.solde) }}</p>
      </div>
      <div class="sum-item">
        <p class="sum-label">P&L</p>
        <p :class="['sum-val', parseFloat(activeAcc.pnl_total) >= 0 ? 'pos' : 'neg']">
          {{ parseFloat(activeAcc.pnl_total) >= 0 ? '+' : '' }}{{ fmtUsd(activeAcc.pnl_total) }}
        </p>
      </div>
      <div class="sum-item">
        <p class="sum-label">{{ lang === 'fr' ? 'Performance' : '收益率' }}</p>
        <p :class="['sum-val', activeAcc.pnl_pct >= 0 ? 'pos' : 'neg']">
          {{ activeAcc.pnl_pct >= 0 ? '+' : '' }}{{ activeAcc.pnl_pct?.toFixed(2) }}%
        </p>
      </div>
    </div>

    <!-- POSITIONS + TRADING -->
    <div v-if="activeAcc" class="section two-col">

      <!-- Positions -->
      <div class="panel">
        <h3 class="panel-title">{{ t('port.positions') }}</h3>
        <div v-if="positions.length === 0" class="empty">{{ t('port.no_pos') }}</div>
        <div v-for="pos in (positions || [])" :key="pos.id" class="position-row">
          <div class="pos-left">
            <span class="pos-sym">{{ pos.symbol?.replace('USDT','') }}</span>
            <span class="pos-qty">{{ pos.quantite ? parseFloat(pos.quantite).toFixed(6) : '0' }}</span>
          </div>
          <div class="pos-mid">
            <p class="pos-entry">{{ lang === 'fr' ? 'Entrée' : '买入价' }} : {{ fmtUsd(pos.prix_moyen) }}</p>
            <p class="pos-current">{{ lang === 'fr' ? 'Actuel' : '当前价' }} : {{ fmtUsd(pos.prix_actuel) }}</p>
          </div>
          <div class="pos-right">
            <p class="pos-val">{{ fmtUsd(pos.valeur_actuelle) }}</p>
            <p :class="['pos-pnl', pos.pnl_pct >= 0 ? 'pos' : 'neg']">
              {{ pos.pnl_pct >= 0 ? '+' : '' }}{{ pos.pnl_pct != null ? pos.pnl_pct.toFixed(2) : '0.00' }}%
            </p>
          </div>
          <button class="btn-sell" @click="openSell(pos)">{{ t('port.sell') }}</button>
        </div>
      </div>

      <!-- Formulaire ordre -->
      <div class="panel">
        <h3 class="panel-title">{{ t('port.order') }}</h3>
        <div class="sym-row">
          <button v-for="s in SYMBOLS" :key="s"
            class="sym-btn" :class="{ active: orderForm.symbol === s }"
            @click="orderForm.symbol = s; orderForm.type = 'BUY'">
            {{ s.replace('USDT','') }}
          </button>
        </div>
        <div class="type-row">
          <button :class="['type-btn', orderForm.type==='BUY'  ? 'active-buy'  : '']" @click="orderForm.type='BUY'">{{ t('port.buy') }}</button>
          <button :class="['type-btn', orderForm.type==='SELL' ? 'active-sell' : '']" @click="orderForm.type='SELL'">{{ t('port.sell') }}</button>
        </div>
        <div v-if="orderForm.type === 'BUY'">
          <label class="lbl">{{ lang === 'fr' ? 'Montant à investir ($)' : '投资金额 ($)' }}</label>
          <input v-model.number="orderForm.montant" class="input" type="number" placeholder="ex: 500" />
          <p class="hint">{{ t('port.available') }} : {{ fmtUsd(activeAcc.solde) }}</p>
        </div>
        <div v-else>
          <label class="lbl">{{ lang === 'fr' ? 'Quantité à vendre' : '卖出数量' }}</label>
          <input v-model.number="orderForm.quantite" class="input" type="number" placeholder="ex: 0.005" />
          <p v-if="currentPos" class="hint">{{ t('port.available') }} : {{ currentPos.quantite }}</p>
        </div>
        <div class="fees-row">
          <span>{{ t('port.fees') }}</span>
          <span>{{ fmtUsd(estimatedFees) }}</span>
        </div>
        <div v-if="orderError"   class="error">{{ orderError }}</div>
        <div v-if="orderSuccess" class="success">{{ orderSuccess }}</div>
        <button class="btn-order" :class="orderForm.type === 'BUY' ? 'btn-buy' : 'btn-sell-full'"
          :disabled="orderLoading" @click="placeOrder">
          {{ orderLoading
            ? (lang === 'fr' ? 'Exécution...' : '执行中...')
            : orderForm.type === 'BUY'
              ? `${t('port.buy')} ${orderForm.symbol?.replace('USDT','')}`
              : `${t('port.sell')} ${orderForm.symbol?.replace('USDT','')}` }}
        </button>
      </div>
    </div>

    <!-- HISTORIQUE -->
    <div v-if="activeAcc && trades.length" class="section">
      <h2>{{ t('port.history') }} — {{ activeAcc.nom }}</h2>
      <table class="trade-table">
        <thead>
          <tr>
            <th>{{ lang === 'fr' ? 'Date' : '日期' }}</th>
            <th>{{ lang === 'fr' ? 'Type' : '类型' }}</th>
            <th>Crypto</th>
            <th>{{ lang === 'fr' ? 'Quantité' : '数量' }}</th>
            <th>{{ lang === 'fr' ? 'Prix exec.' : '成交价' }}</th>
            <th>{{ lang === 'fr' ? 'Montant' : '金额' }}</th>
            <th>{{ lang === 'fr' ? 'Frais' : '手续费' }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in trades" :key="t.id">
            <td>{{ fmtDate(t.executed_at) }}</td>
            <td><span :class="['badge', t.type==='BUY' ? 'badge-green' : 'badge-red']">{{ t.type }}</span></td>
            <td>{{ t.symbol?.replace('USDT','') }}</td>
            <td>{{ parseFloat(t.quantite).toFixed(6) }}</td>
            <td>{{ fmtUsd(t.prix_exec) }}</td>
            <td>{{ fmtUsd(t.montant_eur) }}</td>
            <td class="fees">{{ fmtUsd(t.frais) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</template>

<script setup>
import { useLang } from '../composables/useLang'

const { lang, t } = useLang()
const config = useRuntimeConfig()
const API    = config.public.apiBase

const getHeaders = () => {
  const token = process.client ? localStorage.getItem('access_token') ?? '' : ''
  return { Authorization: `Bearer ${token}` }
}

const SYMBOLS = ['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT']
const accounts     = ref([])
const activeAcc    = ref(null)
const positions    = ref([])
const trades       = ref([])
const showCreate   = ref(false)
const newName      = ref('')
const orderLoading = ref(false)
const orderError   = ref('')
const orderSuccess = ref('')
const orderForm    = reactive({ symbol: 'BTCUSDT', type: 'BUY', montant: null, quantite: null })

const fmtUsd  = v => '$' + parseFloat(v || 0).toLocaleString('en-US', { minimumFractionDigits:2, maximumFractionDigits:2 })
const fmtDate = d => new Date(d).toLocaleString('fr-FR', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' })

const currentPos    = computed(() => positions.value.find(p => p.symbol === orderForm.symbol))
const estimatedFees = computed(() => orderForm.type === 'BUY' && orderForm.montant ? (orderForm.montant * 0.001).toFixed(2) : '0.00')

async function loadAccounts() {
  try {
    accounts.value = await $fetch(`${API}/accounts/`, { headers: getHeaders() })
    if (accounts.value.length && !activeAcc.value) await selectAcc(accounts.value[0])
  } catch (e) { console.error('Erreur comptes:', e) }
}

async function selectAcc(acc) {
  try {
    const res = await $fetch(`${API}/accounts/${acc.id}/`, { headers: getHeaders() })
    activeAcc.value = res.account
    positions.value = res.positions
    trades.value    = await $fetch(`${API}/accounts/${acc.id}/trades/`, { headers: getHeaders() })
  } catch (e) { console.error('Erreur sélection:', e) }
}

async function createAccount() {
  if (!newName.value.trim()) return
  try {
    const acc = await $fetch(`${API}/accounts/`, { method: 'POST', headers: getHeaders(), body: { nom: newName.value } })
    accounts.value.push(acc)
    showCreate.value = false
    newName.value    = ''
    await selectAcc(acc)
  } catch (e) { console.error('Erreur création:', e?.data?.error ?? e) }
}

function openSell(pos) {
  orderForm.symbol   = pos.symbol
  orderForm.type     = 'SELL'
  orderForm.quantite = parseFloat(pos.quantite)
}

async function placeOrder() {
  orderError.value = ''; orderSuccess.value = ''
  if (orderForm.type === 'BUY'  && !orderForm.montant)  { orderError.value = lang.value === 'fr' ? 'Entrez un montant' : '请输入金额'; return }
  if (orderForm.type === 'SELL' && !orderForm.quantite) { orderError.value = lang.value === 'fr' ? 'Entrez une quantité' : '请输入数量'; return }
  orderLoading.value = true
  try {
    const body = orderForm.type === 'BUY'
      ? { symbol: orderForm.symbol, type: 'BUY',  montant:  orderForm.montant }
      : { symbol: orderForm.symbol, type: 'SELL', quantite: orderForm.quantite }
    const res = await $fetch(`${API}/accounts/${activeAcc.value.id}/order/`, { method: 'POST', headers: getHeaders(), body })
    orderSuccess.value = res.message
    orderForm.montant  = null
    orderForm.quantite = null
    await selectAcc(activeAcc.value)
    await loadAccounts()
    setTimeout(() => { orderSuccess.value = '' }, 4000)
  } catch (e) {
    orderError.value = e?.data?.error ?? (lang.value === 'fr' ? "Erreur lors de l'ordre" : '下单失败')
  } finally { orderLoading.value = false }
}

onMounted(loadAccounts)
</script>

<style scoped>
.page { min-height:100vh; background:linear-gradient(160deg,#060810,#0a0f1e); max-width:1200px; margin:0 auto; padding:24px; color:#f1f5f9; }
.section { margin-bottom:28px; }
.section-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }
.section-head h2, h2 { font-size:16px; font-weight:700; }
.accounts-tabs { display:flex; gap:10px; flex-wrap:wrap; }
.account-tab { background:#0d1117; border:1px solid #1e2535; border-radius:12px; padding:16px 20px; cursor:pointer; transition:all .15s; min-width:220px; flex:1; }
.account-tab:hover, .account-tab.active { border-color:#7c3aed; background:rgba(124,58,237,.08); }
.tab-top   { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
.tab-name  { font-weight:600; font-size:14px; }
.tab-badge { background:#1e2535; color:#6b7280; font-size:10px; border-radius:4px; padding:2px 8px; }
.tab-value { font-size:22px; font-weight:700; color:#f1f5f9; white-space:nowrap; }
.tab-pnl   { font-size:13px; font-weight:600; margin:2px 0; }
.tab-solde { color:#4b5563; font-size:12px; margin-top:4px; }
.summary-bar { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:24px; }
.sum-item { background:#0d1117; border:1px solid #1e2535; border-radius:10px; padding:12px 16px; }
.sum-label{ color:#6b7280; font-size:10px; text-transform:uppercase; letter-spacing:1px; margin:0; }
.sum-val  { font-size:18px; font-weight:700; margin:4px 0 0; }
.two-col { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.panel { background:linear-gradient(135deg,#0d1117,#0f1520); border:1px solid #1e2535; border-radius:16px; padding:20px; }
.panel-title { font-size:14px; font-weight:700; margin-bottom:16px; }
.position-row { display:flex; align-items:center; gap:10px; padding:10px 0; border-bottom:1px solid #1e2535; }
.position-row:last-child { border-bottom:none; }
.pos-left  { min-width:80px; } .pos-sym { font-weight:700; font-size:14px; margin-right:6px; } .pos-qty { color:#6b7280; font-size:11px; display:block; }
.pos-mid   { flex:1; } .pos-entry { color:#4b5563; font-size:11px; margin:0; } .pos-current { color:#6b7280; font-size:11px; margin:2px 0 0; }
.pos-right { text-align:right; min-width:90px; } .pos-val { font-weight:600; font-size:13px; margin:0; } .pos-pnl { font-size:12px; margin:2px 0 0; }
.empty { color:#4b5563; font-size:13px; padding:16px 0; }
.pos { color:#10b981; } .neg { color:#ef4444; }
.sym-row { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px; }
.sym-btn { background:#060810; border:1px solid #1e2535; color:#9ca3af; border-radius:6px; padding:5px 10px; font-size:12px; font-weight:600; cursor:pointer; }
.sym-btn.active { border-color:#7c3aed; color:#a78bfa; background:rgba(124,58,237,.1); }
.type-row { display:flex; gap:8px; margin-bottom:14px; }
.type-btn { flex:1; border-radius:8px; padding:9px; font-size:13px; font-weight:600; cursor:pointer; border:1px solid #1e2535; background:#060810; color:#6b7280; }
.active-buy  { border-color:#10b981; color:#10b981; background:rgba(16,185,129,.1); }
.active-sell { border-color:#ef4444; color:#ef4444; background:rgba(239,68,68,.1); }
.input { background:#060810; border:1px solid #1e2535; color:#f1f5f9; border-radius:8px; padding:9px 14px; font-size:13px; outline:none; width:100%; }
.input:focus { border-color:#7c3aed; }
.lbl  { display:block; color:#6b7280; font-size:11px; text-transform:uppercase; letter-spacing:1px; margin-bottom:6px; margin-top:4px; }
.hint { color:#4b5563; font-size:11px; margin-top:4px; }
.fees-row { display:flex; justify-content:space-between; color:#4b5563; font-size:12px; padding:8px 0; border-top:1px solid #1e2535; margin-top:8px; }
.error   { background:rgba(239,68,68,.1);  border:1px solid #ef4444; color:#ef4444; border-radius:8px; padding:8px 12px; font-size:13px; margin-top:8px; }
.success { background:rgba(16,185,129,.1); border:1px solid #10b981; color:#10b981; border-radius:8px; padding:8px 12px; font-size:13px; margin-top:8px; }
.btn-order { width:100%; border:none; border-radius:8px; padding:12px; font-size:14px; font-weight:700; cursor:pointer; margin-top:12px; transition:opacity .15s; }
.btn-order:hover:not(:disabled) { opacity:.85; } .btn-order:disabled { opacity:.5; cursor:wait; }
.btn-buy      { background:linear-gradient(135deg,#059669,#10b981); color:white; }
.btn-sell-full{ background:linear-gradient(135deg,#dc2626,#ef4444); color:white; }
.btn-sell     { background:rgba(239,68,68,.1); border:1px solid #ef4444; color:#ef4444; border-radius:6px; padding:4px 10px; font-size:11px; cursor:pointer; white-space:nowrap; flex-shrink:0; }
.create-box { display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap; }
.btn-add    { background:rgba(124,58,237,.15); border:1px solid #7c3aed; color:#a78bfa; border-radius:8px; padding:8px 14px; font-size:13px; cursor:pointer; }
.btn-primary{ background:linear-gradient(135deg,#7c3aed,#2563eb); border:none; color:white; border-radius:8px; padding:9px 18px; font-size:13px; font-weight:600; cursor:pointer; }
.btn-cancel { background:transparent; border:1px solid #374151; color:#6b7280; border-radius:8px; padding:9px 14px; font-size:13px; cursor:pointer; }
.trade-table { width:100%; border-collapse:collapse; font-size:13px; margin-top:12px; }
.trade-table th { color:#4b5563; font-size:11px; text-transform:uppercase; letter-spacing:1px; padding:8px 12px; text-align:left; border-bottom:1px solid #1e2535; }
.trade-table td { padding:10px 12px; border-bottom:1px solid #1e2535; color:#9ca3af; }
.trade-table tr:last-child td { border-bottom:none; }
.fees { color:#4b5563; }
.badge { font-size:11px; border-radius:4px; padding:2px 8px; font-weight:600; }
.badge-green { background:rgba(16,185,129,.15); color:#10b981; }
.badge-red   { background:rgba(239,68,68,.15);  color:#ef4444; }
@media(max-width:768px) { .two-col { grid-template-columns:1fr; } .summary-bar { grid-template-columns:1fr 1fr; } }
</style>