import type { Ref } from 'vue'

// ── Types
export interface ForecastPoint  { date: string; price: number }
export interface ModelInfo      { rmse: number; mae: number; mape: number; version: string; run_id: string }
export interface XGBSignal      { direction: 0 | 1; probability: number; signal: 'HAUSSE' | 'BAISSE'; confidence: 'Forte' | 'Moyenne' | 'Faible' }
export interface PredictionResult {
  symbol:     string
  generated:  string
  forecast:   ForecastPoint[]
  model_info: ModelInfo
  xgb_signal?: XGBSignal      // optionnel : ajouté quand XGBoost est entraîné
}

export const usePrediction = (symbol: Ref<string> | string) => {
  const config  = useRuntimeConfig()
  const apiBase = config.public.apiBase

  const sym = typeof symbol === 'string' ? symbol : symbol

  const prediction = ref<PredictionResult | null>(null)
  const xgbSignal  = ref<XGBSignal | null>(null)
  const loading    = ref(false)
  const error      = ref<string | null>(null)
  let   refreshTimer: ReturnType<typeof setInterval> | null = null

  // ── Prédiction LSTM (7 jours de prix)
  const fetchPrediction = async () => {
    loading.value = true
    error.value   = null
    try {
      const s = typeof sym === 'string' ? sym : sym.value
      prediction.value = await $fetch<PredictionResult>(`${apiBase}/predict/${s}/`)

      // Récupérer le signal XGBoost en même temps si disponible
      await fetchXGBSignal()
    } catch (e: any) {
      error.value = e?.data?.error ?? 'Erreur de connexion'
    } finally {
      loading.value = false
    }
  }

  // ── Signal XGBoost (direction J+1)
  const fetchXGBSignal = async () => {
    try {
      const s = typeof sym === 'string' ? sym : sym.value
      xgbSignal.value = await $fetch<XGBSignal>(`${apiBase}/predict/${s}/direction/`)
    } catch {
      xgbSignal.value = null  // XGBoost pas encore entraîné → silencieux
    }
  }

  // ── Déclencher un entraînement
  const triggerTraining = async () => {
    const s   = typeof sym === 'string' ? sym : sym.value
    const res = await $fetch<{ task_id: string }>(`${apiBase}/train/`, {
      method: 'POST',
      body:   { symbol: s },
    })
    return res.task_id
  }

  // ── Polling du statut Celery
  const pollStatus = (taskId: string): Promise<string> =>
    new Promise(resolve => {
      const iv = setInterval(async () => {
        const r = await $fetch<{ status: string }>(`${apiBase}/train/${taskId}/status/`)
        if (r.status === 'SUCCESS' || r.status === 'FAILURE') {
          clearInterval(iv)
          if (r.status === 'SUCCESS') await fetchPrediction()
          resolve(r.status)
        }
      }, 3000)
    })

  // ── Prix actuel (dernier point historique)
  const prixActuel = computed(() => {
    if (!prediction.value?.forecast?.length) return null
    return prediction.value.forecast[0].price
  })

  // ── Variation prédite J+1 vs aujourd'hui
  const variationJ1 = computed(() => {
    if (!prediction.value?.forecast?.length || !prixActuel.value) return null
    const j1  = prediction.value.forecast[0].price
    const now = prixActuel.value
    return { valeur: j1, pct: ((j1 - now) / now * 100).toFixed(2), hausse: j1 >= now }
  })

  // ── Refresh auto quand le symbole change (si Ref)
  if (typeof sym !== 'string') {
    watch(sym, () => fetchPrediction())
  }

  onMounted(() => {
    fetchPrediction()
    refreshTimer = setInterval(fetchPrediction, 3_600_000)
  })

  onUnmounted(() => {
    if (refreshTimer) clearInterval(refreshTimer)
  })

  return {
    prediction,
    xgbSignal,
    loading,
    error,
    prixActuel,
    variationJ1,
    fetchPrediction,
    fetchXGBSignal,
    triggerTraining,
    pollStatus,
  }
}