from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from decimal import Decimal


class User(AbstractUser):
    """
    Utilisateur de base.
    Login : username + password (pas d'email requis).
    """
    email = models.EmailField(blank=True)

    def __str__(self):
        return self.username


class VirtualAccount(models.Model):
    """
    Compte de trading virtuel.
    Un user peut en avoir plusieurs (max 3 par défaut).
    Chaque compte démarre avec 10 000 €.
    """
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="accounts")
    nom        = models.CharField(max_length=50)
    solde      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("10000.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "nom")
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user.username} — {self.nom} ({self.solde} €)"

    @property
    def valeur_totale(self):
        """Solde EUR + valeur actuelle de toutes les positions."""
        valeur_positions = sum(p.valeur_actuelle for p in self.positions.all())
        return self.solde + valeur_positions

    @property
    def pnl_total(self):
        """P&L total depuis la création (par rapport aux 10 000 € initiaux)."""
        return self.valeur_totale - Decimal("10000.00")

    @property
    def pnl_pct(self):
        return round(float(self.pnl_total / Decimal("100.00")), 2)


SYMBOLS = [
    ("BTCUSDT", "Bitcoin"),
    ("ETHUSDT", "Ethereum"),
    ("BNBUSDT", "BNB"),
    ("SOLUSDT", "Solana"),
    ("XRPUSDT", "XRP"),
]

class Position(models.Model):
    """
    Crypto détenue dans un compte virtuel.
    Une ligne par (compte, symbole).
    Mise à jour à chaque achat/vente.
    """
    account        = models.ForeignKey(VirtualAccount, on_delete=models.CASCADE, related_name="positions")
    symbol         = models.CharField(max_length=20, choices=SYMBOLS)
    quantite       = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal("0"))
    prix_moyen     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    # prix_actuel est mis à jour par le service de prix (yfinance/CoinGecko)
    prix_actuel    = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("account", "symbol")
        ordering = ["symbol"]

    def __str__(self):
        return f"{self.account} — {self.symbol} x{self.quantite}"

    @property
    def valeur_actuelle(self):
        return self.quantite * self.prix_actuel

    @property
    def pnl(self):
        """P&L non réalisé de cette position."""
        return (self.prix_actuel - self.prix_moyen) * self.quantite

    @property
    def pnl_pct(self):
        if self.prix_moyen == 0:
            return Decimal("0")
        return round(float((self.prix_actuel - self.prix_moyen) / self.prix_moyen * 100), 2)


class Trade(models.Model):
    """
    Historique de chaque ordre exécuté.
    Immuable : on ne modifie jamais un trade enregistré.
    """
    BUY  = "BUY"
    SELL = "SELL"
    TYPE_CHOICES = [(BUY, "Achat"), (SELL, "Vente")]

    account      = models.ForeignKey(VirtualAccount, on_delete=models.CASCADE, related_name="trades")
    symbol       = models.CharField(max_length=20, choices=SYMBOLS)
    type         = models.CharField(max_length=4, choices=TYPE_CHOICES)
    quantite     = models.DecimalField(max_digits=18, decimal_places=8)
    prix_exec    = models.DecimalField(max_digits=12, decimal_places=2)
    montant_eur  = models.DecimalField(max_digits=12, decimal_places=2)
    frais        = models.DecimalField(max_digits=10, decimal_places=4)
    solde_avant  = models.DecimalField(max_digits=12, decimal_places=2)
    solde_apres  = models.DecimalField(max_digits=12, decimal_places=2)
    executed_at  = models.DateTimeField(auto_now_add=True)

    prediction_id = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-executed_at"]

    def __str__(self):
        return f"{self.type} {self.quantite} {self.symbol} @ {self.prix_exec} €"


class LeaderboardEntry(models.Model):
    """
    Snapshot du classement, recalculé par Celery toutes les heures.
    """
    account      = models.OneToOneField(VirtualAccount, on_delete=models.CASCADE, related_name="leaderboard")
    rang         = models.IntegerField(default=0)
    valeur_totale = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("10000.00"))
    pnl_eur      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    pnl_pct      = models.FloatField(default=0.0)
    nb_trades    = models.IntegerField(default=0)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["rang"]

    def __str__(self):
        return f"#{self.rang} {self.account.user.username} — {self.account.nom} ({self.pnl_pct:+.2f}%)"