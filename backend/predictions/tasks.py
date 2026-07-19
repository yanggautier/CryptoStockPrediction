import os, logging
from celery import shared_task
from django.utils import timezone   
from django.core.cache import cache

log = logging.getLogger(__name__)


@shared_task(bind=True, queue="training")
def train_model_task(self, symbol: str, job_id: int):
    from predictions.models import TrainingJob, ModelMetric
    from predictions.views import ModelLoader

    job = TrainingJob.objects.get(id=job_id)
    job.task_id = self.request.id
    job.status  = TrainingJob.RUNNING
    job.save(update_fields=["task_id", "status"])

    try:
        import sys
        sys.path.insert(0, "/app/ml")

        # Etape 1 : Donnees
        job.update_progress(5, "Verification des donnees...")
        csv_path = f"/app/ml/data/{symbol}_1d.csv"
        from datetime import datetime, timedelta

        data_fresh = (
            os.path.exists(csv_path) and
            datetime.fromtimestamp(os.path.getmtime(csv_path)) > datetime.now() - timedelta(hours=24)
        )

        if data_fresh:
            job.add_log("Donnees recentes trouvees — collecte ignoree")
            job.update_progress(20, "Donnees OK")
        else:
            job.add_log("Collecte des donnees...")
            from data_collector import build_dataset, save_to_csv
            df = build_dataset(symbol)
            save_to_csv(df, symbol)
            _save_to_db(df, symbol)
            job.update_progress(20, "Donnees collectees")
            job.add_log(f"Dataset : {len(df)} lignes, {len(df.columns)} features")

        # Etape 2 : LSTM
        job.update_progress(25, "Entrainement LSTM...")
        job.add_log("LSTM — debut entrainement")

        from train_model import train_with_mlflow
        run_id, lstm_metrics, future = train_with_mlflow(symbol)

        job.update_progress(70, "LSTM termine")
        job.add_log(f"LSTM — RMSE: ${lstm_metrics['rmse']:,.0f} | MAPE: {lstm_metrics['mape']:.2f}%")

        ModelMetric.objects.create(
            symbol=symbol,
            model_type=ModelMetric.LSTM,
            rmse=lstm_metrics["rmse"],
            mae=lstm_metrics["mae"],
            mape=lstm_metrics["mape"],
            run_id=run_id,
            model_version=ModelMetric.next_version(symbol, ModelMetric.LSTM),
            model_stage="Production",
        )

        # Etape 3 : XGBoost
        job.update_progress(72, "Entrainement XGBoost...")
        job.add_log("XGBoost — debut entrainement")
        xgb_metrics = {}
        prediction  = {}
        try:
            from xgboost_model import run as run_xgb
            _, xgb_metrics, prediction = run_xgb(symbol)
            job.update_progress(92, "XGBoost termine")
            job.add_log(f"XGBoost — Accuracy: {xgb_metrics['accuracy']*100:.1f}%")
            job.add_log(f"Signal demain : {prediction['signal']} ({prediction['probability']*100:.0f}%)")
            ModelMetric.objects.create(
                symbol=symbol,
                model_type=ModelMetric.XGBOOST,
                accuracy=xgb_metrics.get("accuracy"),
                f1=xgb_metrics.get("f1"),
                auc_roc=xgb_metrics.get("auc_roc"),
                run_id=run_id,
                model_version=ModelMetric.next_version(symbol, ModelMetric.XGBOOST),
                model_stage="Production",
            )
        except Exception as e:
            job.add_log(f"XGBoost ignore : {e}")
            job.update_progress(92, "XGBoost ignore")

        # Etape 4 : Finalisation
        job.update_progress(97, "Finalisation...")
        ModelLoader.reload(symbol)
        cache.delete(f"pred_{symbol}")

        job.lstm_rmse    = lstm_metrics["rmse"]
        job.lstm_mape    = lstm_metrics["mape"]
        job.xgb_accuracy = xgb_metrics.get("accuracy")
        job.run_id       = run_id
        job.status       = TrainingJob.SUCCESS
        job.progress     = 100
        job.current_step = "Entrainement termine"
        job.finished_at  = timezone.now()
        job.save()
        job.add_log("=== Entrainement termine avec succes ===")
        return {"run_id": run_id, "lstm": lstm_metrics, "xgb": xgb_metrics}

    except Exception as exc:
        job.status       = TrainingJob.FAILURE
        job.current_step = f"Erreur : {str(exc)[:200]}"
        job.finished_at  = timezone.now()
        job.save()
        job.add_log(f"ERREUR : {exc}")
        raise


@shared_task(queue="default")
def collect_data_task():
    import sys; sys.path.insert(0, "/app/ml")
    from data_collector import run
    datasets = run(save_mode="both")
    return {sym: len(df) for sym, df in datasets.items() if df is not None}


@shared_task(queue="default")
def collect_news_task():
    import sys; sys.path.insert(0, "/app/ml")
    from news_collector import run as collect_news
    return collect_news(days_back=1)


@shared_task(queue="default")
def mlops_report_task():
    import sys; sys.path.insert(0, "/app/ml")
    from mlops_monitor import auto_retrain
    return auto_retrain()


@shared_task(queue="default")
def update_prices_task():
    import yfinance as yf
    from users.models import Position
    YAHOO = {
        "BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD",
        "BNBUSDT": "BNB-USD", "SOLUSDT": "SOL-USD", "XRPUSDT": "XRP-USD",
    }
    symbols = Position.objects.values_list("symbol", flat=True).distinct()
    updated = 0
    for symbol in symbols:
        try:
            hist  = yf.Ticker(YAHOO[symbol]).history(period="1d", interval="1m")
            if hist.empty: continue
            price = round(float(hist["Close"].iloc[-1]), 2)
            Position.objects.filter(symbol=symbol).update(prix_actuel=price)
            updated += 1
        except Exception as e:
            log.warning(f"Prix {symbol} indisponible : {e}")
    return f"{updated} symboles mis a jour"


@shared_task(queue="default")
def update_leaderboard_task():
    from users.models import VirtualAccount, LeaderboardEntry
    accounts = VirtualAccount.objects.filter(is_active=True)
    scores   = sorted(
        [(acc, float(acc.valeur_totale)) for acc in accounts],
        key=lambda x: x[1], reverse=True,
    )
    for rang, (acc, valeur) in enumerate(scores, 1):
        pnl = valeur - 10000
        LeaderboardEntry.objects.update_or_create(
            account=acc,
            defaults={
                "rang": rang, "valeur_totale": valeur,
                "pnl_eur": pnl, "pnl_pct": pnl / 100.0,
                "nb_trades": acc.trades.count(),
            }
        )
    return f"{len(scores)} comptes mis a jour"


def _save_to_db(df, symbol: str):
    from predictions.models import OHLCVData, MacroData, FearGreedData, FuturesData
    from django.db import transaction

    macro_cols   = ["dxy","dxy_returns","sp500","sp500_returns","nasdaq",
                    "nasdaq_returns","gold","gold_returns","oil","oil_returns","vix"]
    futures_cols = ["funding_rate","open_interest"]

    with transaction.atomic():
        OHLCVData.objects.filter(symbol=symbol).delete()
        OHLCVData.objects.bulk_create([
            OHLCVData(
                symbol=symbol, timestamp=ts.date(),
                open=row.get("open",0),  high=row.get("high",0),
                low=row.get("low",0),    close=row.get("close",0),
                volume=row.get("volume",0),
                rsi=row.get("rsi"),      macd=row.get("macd"),
                macd_signal=row.get("macd_signal"), macd_diff=row.get("macd_diff"),
                bb_upper=row.get("bb_upper"),   bb_middle=row.get("bb_middle"),
                bb_lower=row.get("bb_lower"),   bb_width=row.get("bb_width"),
                price_ma7=row.get("price_ma7"), price_ma30=row.get("price_ma30"),
                price_ma90=row.get("price_ma90"),volume_ma7=row.get("volume_ma7"),
                returns=row.get("returns"),     log_returns=row.get("log_returns"),
                volatility=row.get("volatility"),
                target_direction=row.get("target_direction"),
                target_price=row.get("target_price"),
            )
            for ts, row in df.iterrows()
        ], ignore_conflicts=True)

        if any(c in df.columns for c in macro_cols):
            MacroData.objects.all().delete()
            MacroData.objects.bulk_create([
                MacroData(timestamp=ts.date(), **{c: row.get(c) for c in macro_cols if c in df.columns})
                for ts, row in df.iterrows()
            ], ignore_conflicts=True)

        if "fear_greed" in df.columns:
            FearGreedData.objects.all().delete()
            FearGreedData.objects.bulk_create([
                FearGreedData(timestamp=ts.date(),
                    fear_greed=row.get("fear_greed",50),
                    fear_greed_norm=row.get("fear_greed_norm",0.5))
                for ts, row in df.iterrows()
            ], ignore_conflicts=True)

        if any(c in df.columns for c in futures_cols):
            FuturesData.objects.filter(symbol=symbol).delete()
            FuturesData.objects.bulk_create([
                FuturesData(symbol=symbol, timestamp=ts.date(),
                    **{c: row.get(c) for c in futures_cols if c in df.columns})
                for ts, row in df.iterrows()
            ], ignore_conflicts=True)