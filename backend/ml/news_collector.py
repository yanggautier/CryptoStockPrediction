import os, logging, requests
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

NEWSAPI_KEY      = os.getenv("NEWSAPI_KEY", "")
CRYPTOPANIC_KEY  = os.getenv("CRYPTOPANIC_API_KEY", "")

SYMBOLS = {
    "BTCUSDT": ["bitcoin", "BTC"],
    "ETHUSDT": ["ethereum", "ETH"],
    "BNBUSDT": ["binance coin", "BNB"],
    "SOLUSDT": ["solana", "SOL"],
    "XRPUSDT": ["ripple", "XRP"],
}

# ──────────────────────────────────────────────
# VADER SENTIMENT
# ──────────────────────────────────────────────

def get_vader():
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        return SentimentIntensityAnalyzer()
    except ImportError:
        log.warning("vaderSentiment non installé — pip install vaderSentiment")
        return None


def analyze_sentiment(text: str, vader) -> float:
    """Retourne un score [-1, +1]."""
    if vader is None or not text:
        return 0.0
    scores = vader.polarity_scores(text)
    return round(scores["compound"], 4)


# ──────────────────────────────────────────────
# NEWSAPI
# ──────────────────────────────────────────────

def fetch_newsapi(keyword: str, days_back: int = 1) -> list:
    """Fetch news depuis NewsAPI (clé gratuite = 100 req/j)."""
    if not NEWSAPI_KEY:
        log.warning("NEWSAPI_KEY non défini — skipping NewsAPI")
        return []

    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q":        keyword,
                "from":     from_date,
                "sortBy":   "publishedAt",
                "language": "en",
                "pageSize": 20,
                "apiKey":   NEWSAPI_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        log.info(f"NewsAPI {keyword} — {len(articles)} articles")
        return articles
    except Exception as e:
        log.warning(f"NewsAPI erreur ({keyword}) : {e}")
        return []


# ──────────────────────────────────────────────
# CRYPTOPANIC
# ──────────────────────────────────────────────

def fetch_cryptopanic(currency: str) -> list:
    """Fetch news CryptoPanic (vote-based sentiment)."""
    if not CRYPTOPANIC_KEY:
        return []
    try:
        resp = requests.get(
            "https://cryptopanic.com/api/v1/posts/",
            params={
                "auth_token": CRYPTOPANIC_KEY,
                "currencies":  currency,
                "kind":        "news",
                "public":      "true",
            },
            timeout=10,
        )
        return resp.json().get("results", [])
    except Exception as e:
        log.warning(f"CryptoPanic {currency} : {e}")
        return []


def cryptopanic_score(posts: list) -> float:
    """Score sentiment basé sur les votes [-1, +1]."""
    if not posts:
        return 0.0
    scores = []
    for post in posts[:20]:
        votes = post.get("votes", {})
        pos   = votes.get("positive", 0) + votes.get("liked", 0)
        neg   = votes.get("negative", 0) + votes.get("disliked", 0)
        total = pos + neg
        if total > 0:
            scores.append((pos - neg) / total)
    return round(sum(scores) / len(scores), 4) if scores else 0.0


# ──────────────────────────────────────────────
# SAUVEGARDE EN DB
# ──────────────────────────────────────────────

def save_to_db(symbol: str, articles: list, vader, source: str = "newsapi"):
    """Sauvegarde les articles avec sentiment en DB."""
    try:
        import django
        from predictions.models import NewsArticle  # à créer si besoin
        saved = 0
        for art in articles:
            title   = art.get("title", "") or ""
            content = art.get("description", "") or art.get("content", "") or ""
            text    = f"{title}. {content}"
            score   = analyze_sentiment(text, vader)
            try:
                NewsArticle.objects.update_or_create(
                    url=art.get("url", ""),
                    defaults={
                        "symbol":        symbol,
                        "title":         title[:500],
                        "sentiment":     score,
                        "source":        source,
                        "published_at":  art.get("publishedAt"),
                    }
                )
                saved += 1
            except Exception:
                pass
        log.info(f"DB : {saved} articles sauvegardés pour {symbol}")
    except Exception as e:
        log.warning(f"DB save skipped : {e}")


# ──────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ──────────────────────────────────────────────

def run(days_back: int = 1) -> dict:
    """
    Collecte les news pour tous les symboles.
    Retourne un dict symbol → score sentiment moyen.
    """
    log.info(f"=== News Collector (derniers {days_back}j) ===")
    vader   = get_vader()
    results = {}

    for symbol, keywords in SYMBOLS.items():
        currency  = keywords[1]  # ex: "BTC"
        scores    = []

        # 1. NewsAPI
        for kw in keywords:
            articles = fetch_newsapi(kw, days_back)
            for art in articles:
                title   = art.get("title", "") or ""
                content = art.get("description", "") or ""
                score   = analyze_sentiment(f"{title}. {content}", vader)
                scores.append(score)

        # 2. CryptoPanic
        cp_posts = fetch_cryptopanic(currency)
        if cp_posts:
            scores.append(cryptopanic_score(cp_posts))

        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        results[symbol] = avg_score
        log.info(f"{symbol} — sentiment moyen : {avg_score:+.4f} ({len(scores)} signaux)")

    log.info(f"=== News collectées — {len(results)} symboles ===")
    return results


def get_current_sentiment(symbol: str) -> float:
    """Retourne le score sentiment actuel pour un symbole (pour PredictView)."""
    try:
        vader    = get_vader()
        keywords = SYMBOLS.get(symbol, [symbol.replace("USDT", "")])
        scores   = []

        for kw in keywords:
            articles = fetch_newsapi(kw, days_back=1)
            for art in articles[:5]:
                title = art.get("title", "") or ""
                desc  = art.get("description", "") or ""
                score = analyze_sentiment(f"{title}. {desc}", vader)
                scores.append(score)

        return round(sum(scores) / len(scores), 4) if scores else 0.0
    except Exception:
        return 0.0


if __name__ == "__main__":
    results = run(days_back=1)
    print("\n=== Résultats sentiment ===")
    for sym, score in results.items():
        sentiment = "HAUSSIER" if score > 0.1 else "BAISSIER" if score < -0.1 else "NEUTRE"
        print(f"  {sym}: {score:+.4f}  ({sentiment})")