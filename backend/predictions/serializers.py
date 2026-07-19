from rest_framework import serializers
from .models import PredictionResult, ModelMetric


class PredictionResultSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PredictionResult
        fields = (
            "id", "symbol", "date",
            "pred_price", "pred_dir", "confidence",
            "run_id", "model_version", "model_stage",
            "created_at",
        )


class PredictionResultListSerializer(serializers.ModelSerializer):
    """Version allégée pour les listes (sans run_id)."""
    class Meta:
        model  = PredictionResult
        fields = ("date", "pred_price", "pred_dir", "confidence", "model_version")


class ModelMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ModelMetric
        fields = (
            "id", "symbol", "model_type",
            "rmse", "mae", "mape",
            "accuracy", "f1", "auc_roc",
            "run_id", "model_version", "model_stage",
            "created_at",
        )


class ModelMetricSummarySerializer(serializers.ModelSerializer):
    """Version résumée pour le dashboard."""
    class Meta:
        model  = ModelMetric
        fields = (
            "symbol", "model_type",
            "rmse", "mae", "mape",
            "accuracy", "model_version", "model_stage",
            "created_at",
        )