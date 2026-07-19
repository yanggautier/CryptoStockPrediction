export const useLang = () => {
  const lang = useState<'fr'|'zh'>('lang', () => 'fr')

  // Lire localStorage seulement côté client
  if (process.client) {
    const saved = localStorage.getItem('lang') as 'fr'|'zh'
    if (saved) lang.value = saved
  }

  const setLang = (l: 'fr'|'zh') => {
    lang.value = l
    if (process.client) localStorage.setItem('lang', l)
  }

  const toggle = () => setLang(lang.value === 'fr' ? 'zh' : 'fr')

  const t = (key: string): string => {
    const map: Record<string, Record<string, string>> = {
      // Nav
      'nav.dashboard':    { fr: 'Dashboard',    zh: '仪表盘' },
      'nav.portfolio':    { fr: 'Portfolio',    zh: '投资组合' },
      'nav.training':     { fr: 'Entraînement', zh: '训练' },
      'nav.data':         { fr: 'Données',      zh: '数据' },
      'nav.leaderboard':  { fr: 'Classement',   zh: '排行榜' },
      'nav.logout':       { fr: 'Déconnexion',  zh: '退出' },
      'nav.login':        { fr: 'Connexion',    zh: '登录' },
      // Dashboard sections
      'dash.prices':      { fr: 'Prix en temps réel',            zh: '实时价格' },
      'dash.chart':       { fr: 'Prix & Prédiction LSTM',        zh: '价格与 LSTM 预测' },
      'dash.history':     { fr: 'historique + 7j prédiction',    zh: '历史数据 + 7天预测' },
      'dash.forecast':    { fr: 'Prévisions LSTM',               zh: 'LSTM 预测' },
      'dash.metrics':     { fr: 'Métriques du modèle',           zh: '模型指标' },
      'dash.signal':      { fr: 'Signal combiné',                zh: '综合信号' },
      'dash.train_btn':   { fr: 'Entraîner',                    zh: '训练' },
      'dash.current':     { fr: 'Prix actuel',                   zh: '当前价格' },
      'dash.loading':     { fr: 'Chargement...',                 zh: '加载中...' },
      'dash.no_data':     { fr: 'Aucune donnée — lancez un entraînement', zh: '暂无数据 — 请先训练模型' },
      'dash.no_model':    { fr: 'Modèle\nnon entraîné',          zh: '模型\n未训练' },
      'dash.agree':       { fr: 'LSTM et XGBoost sont d\'accord ✓', zh: 'LSTM 与 XGBoost 一致 ✓' },
      'dash.disagree':    { fr: '⚠️ LSTM et XGBoost sont en désaccord', zh: '⚠️ LSTM 与 XGBoost 不一致' },
      'dash.weak':        { fr: 'Signal faible',                 zh: '信号弱' },
      'dash.conf_xgb':    { fr: 'Confiance XGB',                 zh: 'XGB 置信度' },
      'dash.real':        { fr: 'Réel',                          zh: '实际' },
      'dash.production':  { fr: 'Production',                    zh: '生产' },
      'dash.rmse_desc':   { fr: 'Erreur quadratique LSTM',       zh: 'LSTM 均方根误差' },
      'dash.mape_desc':   { fr: 'Erreur relative LSTM',          zh: 'LSTM 平均误差率' },
      'dash.xgb_desc':    { fr: 'Confiance direction J+1',       zh: 'XGB 明日方向置信度' },
      // Periods
      'period.1w':  { fr: '1 sem', zh: '1周' },
      'period.1m':  { fr: '1 mois', zh: '1月' },
      'period.3m':  { fr: '3 mois', zh: '3月' },
      'period.6m':  { fr: '6 mois', zh: '6月' },
      'period.1y':  { fr: '1 an',   zh: '1年' },
      'period.2y':  { fr: '2 ans',  zh: '2年' },
      'period.all': { fr: 'Tout',   zh: '全部' },
      // Signal strength
      'strength.FORT':           { fr: 'FORT',           zh: '强' },
      'strength.MOYEN':          { fr: 'MOYEN',          zh: '中' },
      'strength.CONTRADICTOIRE': { fr: 'CONTRADICTOIRE', zh: '矛盾' },
      // Portfolio
      'port.accounts':   { fr: 'Mes comptes virtuels',    zh: '虚拟账户' },
      'port.new':        { fr: '+ Nouveau compte',        zh: '+ 新建账户' },
      'port.positions':  { fr: 'Positions ouvertes',      zh: '持仓' },
      'port.order':      { fr: 'Passer un ordre',         zh: '下单' },
      'port.history':    { fr: 'Historique des trades',   zh: '交易记录' },
      'port.buy':        { fr: 'Acheter',                 zh: '买入' },
      'port.sell':       { fr: 'Vendre',                  zh: '卖出' },
      'port.fees':       { fr: 'Frais (0.1%)',            zh: '手续费 (0.1%)' },
      'port.available':  { fr: 'Disponible',              zh: '可用' },
      'port.no_pos':     { fr: 'Aucune position ouverte', zh: '暂无持仓' },
      // Leaderboard
      'lb.title':  { fr: '🏆 Classement',                      zh: '🏆 排行榜' },
      'lb.sub':    { fr: 'Top 50 des meilleurs portefeuilles',  zh: '最佳投资组合 Top 50' },
      'conf.Forte':   { fr: 'Forte',   zh: '高' },
      'conf.Moyenne': { fr: 'Moyenne', zh: '中' },
      'conf.Faible':  { fr: 'Faible',  zh: '低' },
    }
    return map[key]?.[lang.value] ?? key
  }

  return { lang, toggle, t }
}