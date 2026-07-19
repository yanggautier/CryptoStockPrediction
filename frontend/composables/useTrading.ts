// ── Types
export interface VirtualAccount {
  id:           number
  nom:          string
  solde:        string
  valeur_totale: string
  pnl_total:    string
  pnl_pct:      number
  nb_trades:    number
  created_at:   string
}

export interface Position {
  id:              number
  symbol:          string
  quantite:        string
  prix_moyen:      string
  prix_actuel:     string
  valeur_actuelle: string
  pnl:             string
  pnl_pct:         number
}

export interface Trade {
  id:          number
  symbol:      string
  type:        'BUY' | 'SELL'
  quantite:    string
  prix_exec:   string
  montant_eur: string
  frais:       string
  solde_avant: string
  solde_apres: string
  executed_at: string
}

export interface OrderPayload {
  symbol:   string
  type:     'BUY' | 'SELL'
  montant?: number    // BUY  : montant EUR à investir
  quantite?: number   // SELL : quantité crypto à vendre
}

export interface OrderResult {
  message: string
  trade:   Trade
  solde:   string
}

export interface LeaderboardEntry {
  rang:         number
  username:     string
  compte_nom:   string
  valeur_totale: string
  pnl_eur:      string
  pnl_pct:      number
  nb_trades:    number
}

// ──────────────────────────────────────────────
// COMPOSABLE
// ──────────────────────────────────────────────

export const useTrading = () => {
  const config    = useRuntimeConfig()
  const apiBase   = config.public.apiBase

  // ── State
  const accounts    = ref<VirtualAccount[]>([])
  const activeAcc   = ref<VirtualAccount | null>(null)
  const positions   = ref<Position[]>([])
  const trades      = ref<Trade[]>([])
  const leaderboard = ref<LeaderboardEntry[]>([])

  const loading     = ref(false)
  const orderLoading = ref(false)
  const error       = ref<string | null>(null)
  const lastTrade   = ref<Trade | null>(null)
  
  const token = computed(() => {
    if (process.client) return localStorage.getItem('access_token') ?? ''
    return ''
  })

  const authHeaders = computed(() => ({
    Authorization: `Bearer ${token.value}`,
  }))

  const register = async (username: string, password: string) => {
    const res = await $fetch<{ tokens: { access: string; refresh: string } }>(
      `${apiBase}/auth/register/`,
      { method: 'POST', body: { username, password, password2: password } }
    )
    _saveTokens(res.tokens)
    return res
  }

  const login = async (username: string, password: string) => {
    const res = await $fetch<{ access: string; refresh: string }>(
      `${apiBase}/auth/login/`,
      { method: 'POST', body: { username, password } }
    )
    _saveTokens(res)
    await fetchAccounts()
    return res
  }

  const logout = () => {
    if (process.client) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
    accounts.value  = []
    activeAcc.value = null
    positions.value = []
  }

  const _saveTokens = (tokens: { access: string; refresh: string }) => {
    if (process.client) {
      localStorage.setItem('access_token',  tokens.access)
      localStorage.setItem('refresh_token', tokens.refresh)
    }
  }

  const isLoggedIn = computed(() => !!token.value)

  const fetchAccounts = async () => {
    loading.value = true
    try {
      accounts.value = await $fetch<VirtualAccount[]>(`${apiBase}/accounts/`, {
        headers: authHeaders.value,
      })
      if (accounts.value.length && !activeAcc.value) {
        await selectAccount(accounts.value[0])
      }
    } catch (e: any) {
      error.value = e?.data?.error ?? 'Erreur chargement comptes'
    } finally {
      loading.value = false
    }
  }

  const selectAccount = async (account: VirtualAccount) => {
    activeAcc.value = account
    await Promise.all([fetchPositions(), fetchTrades()])
  }

  const createAccount = async (nom: string) => {
    const acc = await $fetch<VirtualAccount>(`${apiBase}/accounts/`, {
      method:  'POST',
      headers: authHeaders.value,
      body:    { nom },
    })
    accounts.value.push(acc)
    return acc
  }

  const fetchPositions = async () => {
    if (!activeAcc.value) return
    const res = await $fetch<{ account: VirtualAccount; positions: Position[] }>(
      `${apiBase}/accounts/${activeAcc.value.id}/`,
      { headers: authHeaders.value }
    )
    activeAcc.value = res.account
    positions.value = res.positions
  }

  const fetchTrades = async () => {
    if (!activeAcc.value) return
    trades.value = await $fetch<Trade[]>(
      `${apiBase}/accounts/${activeAcc.value.id}/trades/`,
      { headers: authHeaders.value }
    )
  }

  const placeOrder = async (payload: OrderPayload): Promise<OrderResult> => {
    if (!activeAcc.value) throw new Error('Aucun compte sélectionné')
    orderLoading.value = true
    error.value        = null
    try {
      const result = await $fetch<OrderResult>(
        `${apiBase}/accounts/${activeAcc.value.id}/order/`,
        { method: 'POST', headers: authHeaders.value, body: payload }
      )
      lastTrade.value = result.trade
      await fetchPositions()
      await fetchTrades()
      return result
    } catch (e: any) {
      error.value = e?.data?.error ?? "Erreur lors de l'ordre"
      throw e
    } finally {
      orderLoading.value = false
    }
  }

  const buy  = (symbol: string, montant: number)   => placeOrder({ symbol, type: 'BUY',  montant })
  const sell = (symbol: string, quantite: number)  => placeOrder({ symbol, type: 'SELL', quantite })

  const followSignal = async (symbol: string, signal: 'HAUSSE' | 'BAISSE', montantEur = 100) => {
    if (signal === 'HAUSSE') return buy(symbol, montantEur)
    const pos = positions.value.find(p => p.symbol === symbol)
    if (!pos) throw new Error(`Aucune position ${symbol} à vendre`)
    const qteAVendre = parseFloat(pos.quantite) * 0.5
    return sell(symbol, qteAVendre)
  }

  const totalPnl = computed(() => {
    if (!activeAcc.value) return 0
    return parseFloat(activeAcc.value.pnl_total)
  })

  const totalPnlPct = computed(() => activeAcc.value?.pnl_pct ?? 0)

  const soldeDisponible = computed(() => {
    if (!activeAcc.value) return 0
    return parseFloat(activeAcc.value.solde)
  })

  const positionPourSymbol = (symbol: string) =>
    positions.value.find(p => p.symbol === symbol) ?? null

  const fetchLeaderboard = async () => {
    leaderboard.value = await $fetch<LeaderboardEntry[]>(`${apiBase}/leaderboard/`)
  }

  onMounted(async () => {
    if (isLoggedIn.value) await fetchAccounts()
  })

  return {
    accounts, activeAcc, positions, trades, leaderboard,
    loading, orderLoading, error, lastTrade,
    register, login, logout, isLoggedIn,
    fetchAccounts, selectAccount, createAccount,
    fetchPositions, fetchTrades,
    placeOrder, buy, sell, followSignal,
    totalPnl, totalPnlPct, soldeDisponible, positionPourSymbol,
    fetchLeaderboard,
  }
}