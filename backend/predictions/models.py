from django.db import models


class PredictionResult(models.Model):
    symbol        = models.CharField(max_length=20, db_index=True)
    date          = models.DateField(db_index=True)
    pred_price    = models.FloatField()
    pred_dir      = models.IntegerField(null=True)
    confidence    = models.FloatField(null=True)
    run_id        = models.CharField(max_length=64, blank=True)
    model_version = models.IntegerField(null=True)
    model_stage   = models.CharField(max_length=20, default="Production")
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering        = ["symbol", "date"]
        unique_together = ["symbol", "date", "run_id"]
        indexes         = [models.Index(fields=["symbol", "date"])]

    def __str__(self):
        return f"{self.symbol} {self.date} → {self.pred_price}"


class OHLCVData(models.Model):
    """Prix + indicateurs techniques pour chaque crypto."""
    symbol     = models.CharField(max_length=20, db_index=True)
    timestamp  = models.DateField(db_index=True)
    open       = models.FloatField()
    high       = models.FloatField()
    low        = models.FloatField()
    close      = models.FloatField()
    volume     = models.FloatField()
    rsi        = models.FloatField(null=True)
    macd       = models.FloatField(null=True)
    macd_signal= models.FloatField(null=True)
    macd_diff  = models.FloatField(null=True)
    bb_upper   = models.FloatField(null=True)
    bb_middle  = models.FloatField(null=True)
    bb_lower   = models.FloatField(null=True)
    bb_width   = models.FloatField(null=True)
    price_ma7  = models.FloatField(null=True)
    price_ma30 = models.FloatField(null=True)
    price_ma90 = models.FloatField(null=True)
    volume_ma7 = models.FloatField(null=True)
    returns    = models.FloatField(null=True)
    log_returns= models.FloatField(null=True)
    volatility = models.FloatField(null=True)
    target_direction = models.IntegerField(null=True)
    target_price     = models.FloatField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        unique_together = ("symbol", "timestamp")
        ordering = ["symbol", "timestamp"]
        indexes = [models.Index(fields=["symbol", "timestamp"])]
 
    def __str__(self):
        return f"{self.symbol} {self.timestamp} close={self.close}"
 
 
class MacroData(models.Model):
    """Données marchés traditionnels : DXY, SP500, Gold, Oil, VIX."""
    timestamp     = models.DateField(unique=True, db_index=True)
    dxy           = models.FloatField(null=True)
    dxy_returns   = models.FloatField(null=True)
    sp500         = models.FloatField(null=True)
    sp500_returns = models.FloatField(null=True)
    nasdaq        = models.FloatField(null=True)
    nasdaq_returns= models.FloatField(null=True)
    gold          = models.FloatField(null=True)
    gold_returns  = models.FloatField(null=True)
    oil           = models.FloatField(null=True)
    oil_returns   = models.FloatField(null=True)
    vix           = models.FloatField(null=True)
    created_at    = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ["timestamp"]
 
    def __str__(self):
        return f"Macro {self.timestamp}"
 
 
class FearGreedData(models.Model):
    """Fear & Greed Index journalier."""
    timestamp        = models.DateField(unique=True, db_index=True)
    fear_greed       = models.IntegerField()
    fear_greed_norm  = models.FloatField()
    created_at       = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ["-timestamp"]
 
    def __str__(self):
        return f"F&G {self.timestamp} : {self.fear_greed}"
 
 
class FuturesData(models.Model):
    """Funding rate + Open Interest Binance Futures."""
    symbol        = models.CharField(max_length=20, db_index=True)
    timestamp     = models.DateField(db_index=True)
    funding_rate  = models.FloatField(null=True)
    open_interest = models.FloatField(null=True)
    created_at    = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        unique_together = ("symbol", "timestamp")
        ordering = ["symbol", "timestamp"]
 
    def __str__(self):
        return f"Futures {self.symbol} {self.timestamp}"
 

class ModelMetric(models.Model):
    LSTM    = "lstm"
    XGBOOST = "xgboost"
    MODEL_TYPES = [(LSTM, "LSTM"), (XGBOOST, "XGBoost")]

    symbol     = models.CharField(max_length=20, db_index=True)
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES)
    rmse       = models.FloatField(null=True)
    mae        = models.FloatField(null=True)
    mape       = models.FloatField(null=True)
    accuracy   = models.FloatField(null=True)
    f1         = models.FloatField(null=True)
    auc_roc    = models.FloatField(null=True)
    run_id        = models.CharField(max_length=64, blank=True)
    model_version = models.IntegerField(default=1)
    model_stage   = models.CharField(max_length=20, default="Production")
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes  = [models.Index(fields=["symbol", "model_type", "-created_at"])]

    def __str__(self):
        return f"{self.symbol} {self.model_type} v{self.model_version} — MAPE:{self.mape}"

    @classmethod
    def next_version(cls, symbol: str, model_type: str) -> int:
        """Auto-incrément de version par symbole + type."""
        last = cls.objects.filter(symbol=symbol, model_type=model_type).order_by("-model_version").first()
        return (last.model_version + 1) if last else 1

    @classmethod
    def get_production(cls, symbol: str, model_type: str):
        return cls.objects.filter(
            symbol=symbol, model_type=model_type, model_stage="Production"
        ).order_by("-created_at").first()
 
 
class TrainingJob(models.Model):
    """Suivi d'un entraînement lancé depuis le frontend."""
    PENDING  = "PENDING"
    RUNNING  = "RUNNING"
    SUCCESS  = "SUCCESS"
    FAILURE  = "FAILURE"
    STATUS_CHOICES = [
        (PENDING, "En attente"),
        (RUNNING, "En cours"),
        (SUCCESS, "Terminé"),
        (FAILURE, "Erreur"),
    ]
 
    symbol      = models.CharField(max_length=20)
    task_id     = models.CharField(max_length=64, blank=True)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    progress    = models.IntegerField(default=0)       # 0-100
    current_step= models.CharField(max_length=500, blank=True)
    log         = models.TextField(blank=True)         # logs en temps réel
    # Métriques finales
    lstm_rmse   = models.FloatField(null=True)
    lstm_mape   = models.FloatField(null=True)
    xgb_accuracy= models.FloatField(null=True)
    run_id      = models.CharField(max_length=64, blank=True)
    started_at  = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
 
    class Meta:
        ordering = ["-started_at"]
 
    def __str__(self):
        return f"TrainingJob {self.symbol} [{self.status}] {self.progress}%"
 
    def add_log(self, message: str):
        from django.utils import timezone
        ts = timezone.now().strftime("%H:%M:%S")
        self.log += f"[{ts}] {message}\n"
        self.save(update_fields=["log"])
 
    def update_progress(self, progress: int, step: str = ""):
        self.progress     = progress
        self.current_step = step
        self.save(update_fields=["progress", "current_step"])
