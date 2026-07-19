from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import VirtualAccount, Position, Trade, LeaderboardEntry

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, min_length=6)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = ("username", "password", "password2")

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password2": "Les mots de passe ne correspondent pas."})
        return data

    def create(self, validated_data):
        validated_data.pop("password2")
        user = User.objects.create_user(**validated_data)
        VirtualAccount.objects.create(user=user, nom="Mon portefeuille")
        return user


class UserSerializer(serializers.ModelSerializer):
    nb_comptes = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ("id", "username", "date_joined", "nb_comptes")

    def get_nb_comptes(self, obj):
        return obj.accounts.filter(is_active=True).count()
    

class VirtualAccountSerializer(serializers.ModelSerializer):
    valeur_totale = serializers.ReadOnlyField()
    pnl_total     = serializers.ReadOnlyField()
    pnl_pct       = serializers.ReadOnlyField()
    nb_trades     = serializers.SerializerMethodField()

    class Meta:
        model  = VirtualAccount
        fields = (
            "id", "nom", "solde",
            "valeur_totale", "pnl_total", "pnl_pct",
            "nb_trades", "created_at", "is_active",
        )
        read_only_fields = ("solde", "created_at")

    def get_nb_trades(self, obj):
        return obj.trades.count()


class CreateAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model  = VirtualAccount
        fields = ("nom",)

    def validate_nom(self, value):
        user    = self.context["request"].user
        MAX     = 3
        current = user.accounts.filter(is_active=True).count()
        if current >= MAX:
            raise serializers.ValidationError(f"Maximum {MAX} comptes virtuels par utilisateur.")
        if user.accounts.filter(nom=value).exists():
            raise serializers.ValidationError("Vous avez déjà un compte avec ce nom.")
        return value


class PositionSerializer(serializers.ModelSerializer):
    valeur_actuelle = serializers.ReadOnlyField()
    pnl             = serializers.ReadOnlyField()
    pnl_pct         = serializers.ReadOnlyField()

    class Meta:
        model  = Position
        fields = (
            "id", "symbol",
            "quantite", "prix_moyen", "prix_actuel",
            "valeur_actuelle", "pnl", "pnl_pct",
            "updated_at",
        )

class TradeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Trade
        fields = (
            "id", "symbol", "type",
            "quantite", "prix_exec", "montant_eur",
            "frais", "solde_avant", "solde_apres",
            "executed_at",
        )
        read_only_fields = fields


class OrderSerializer(serializers.Serializer):
    """Serializer pour passer un ordre BUY ou SELL."""
    SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]

    symbol   = serializers.ChoiceField(choices=SYMBOLS)
    type     = serializers.ChoiceField(choices=["BUY", "SELL"])
    montant  = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    quantite = serializers.DecimalField(max_digits=18, decimal_places=8, required=False)

    def validate(self, data):
        if data["type"] == "BUY" and not data.get("montant"):
            raise serializers.ValidationError({"montant": "Requis pour un achat."})
        if data["type"] == "SELL" and not data.get("quantite"):
            raise serializers.ValidationError({"quantite": "Requis pour une vente."})
        return data


class LeaderboardSerializer(serializers.ModelSerializer):
    username    = serializers.CharField(source="account.user.username")
    compte_nom  = serializers.CharField(source="account.nom")

    class Meta:
        model  = LeaderboardEntry
        fields = (
            "rang", "username", "compte_nom",
            "valeur_totale", "pnl_eur", "pnl_pct",
            "nb_trades", "updated_at",
        )