from decimal import Decimal
from django.db import transaction
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .models import VirtualAccount, Position, Trade, LeaderboardEntry
from .serializers import (
    RegisterSerializer, UserSerializer,
    VirtualAccountSerializer, CreateAccountSerializer,
    PositionSerializer, TradeSerializer,
    OrderSerializer, LeaderboardSerializer,
)

TAUX_FRAIS  = Decimal("0.001")
MAX_COMPTES = 3


def get_prix_actuel(symbol: str) -> Decimal:
    """
    Prix temps réel via yfinance.
    En production, remplacer par Redis cache mis à jour toutes les 60s.
    """
    import yfinance as yf
    YAHOO = {
        "BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD",
        "BNBUSDT": "BNB-USD", "SOLUSDT": "SOL-USD", "XRPUSDT": "XRP-USD",
    }
    ticker = yf.Ticker(YAHOO[symbol])
    hist   = ticker.history(period="1d", interval="1m")
    if hist.empty:
        raise ValueError(f"Prix indisponible pour {symbol}")
    return Decimal(str(round(float(hist["Close"].iloc[-1]), 2)))


def get_or_check_account(request, account_id) -> VirtualAccount:
    """Récupère un compte et vérifie qu'il appartient à l'user."""
    try:
        account = VirtualAccount.objects.get(id=account_id, user=request.user, is_active=True)
    except VirtualAccount.DoesNotExist:
        return None
    return account


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user    = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                "user":    UserSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access":  str(refresh.access_token),
                },
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "username":     request.user.username,
            "is_staff":     request.user.is_staff,
            "is_superuser": request.user.is_superuser,
        })

class AccountListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Liste tous les comptes de l'user."""
        accounts = request.user.accounts.filter(is_active=True)
        return Response(VirtualAccountSerializer(accounts, many=True).data)

    def post(self, request):
        """Crée un nouveau compte virtuel (max 3)."""
        serializer = CreateAccountSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            account = serializer.save(user=request.user)
            return Response(VirtualAccountSerializer(account).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AccountDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, account_id):
        """Détail d'un compte : solde + positions + stats."""
        account = get_or_check_account(request, account_id)
        if not account:
            return Response({"error": "Compte introuvable."}, status=404)

        positions = account.positions.all()
        return Response({
            "account":   VirtualAccountSerializer(account).data,
            "positions": PositionSerializer(positions, many=True).data,
        })

    def delete(self, request, account_id):
        """Désactive un compte (soft delete)."""
        account = get_or_check_account(request, account_id)
        if not account:
            return Response({"error": "Compte introuvable."}, status=404)
        account.is_active = False
        account.save()
        return Response({"message": "Compte désactivé."})


class OrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, account_id):
        """
        Passe un ordre BUY ou SELL.

        BUY  → body: { symbol, type: "BUY",  montant: 500 }      (500€ à investir)
        SELL → body: { symbol, type: "SELL", quantite: 0.005 }   (quantité à vendre)
        """
        account = get_or_check_account(request, account_id)
        if not account:
            return Response({"error": "Compte introuvable."}, status=404)

        serializer = OrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data   = serializer.validated_data
        symbol = data["symbol"]
        ordre  = data["type"]

        try:
            prix = get_prix_actuel(symbol)
        except Exception as e:
            return Response({"error": f"Prix indisponible : {e}"}, status=503)

        if ordre == "BUY":
            return self._buy(account, symbol, prix, data["montant"])
        else:
            return self._sell(account, symbol, prix, data["quantite"])

    @transaction.atomic
    def _buy(self, account, symbol, prix, montant_eur):
        frais    = (montant_eur * TAUX_FRAIS).quantize(Decimal("0.0001"))
        total    = montant_eur + frais
        quantite = (montant_eur / prix).quantize(Decimal("0.00000001"))

        if account.solde < total:
            return Response({"error": f"Solde insuffisant. Disponible : {account.solde} €"}, status=400)

        solde_avant  = account.solde
        account.solde -= total
        account.save()

        position, created = Position.objects.get_or_create(
            account=account, symbol=symbol,
            defaults={"quantite": 0, "prix_moyen": 0, "prix_actuel": prix},
        )
        if created or position.quantite == 0:
            position.prix_moyen = prix
            position.quantite   = quantite
        else:
            total_val           = position.quantite * position.prix_moyen + quantite * prix
            position.quantite  += quantite
            position.prix_moyen = total_val / position.quantite
        position.prix_actuel = prix
        position.save()

        trade = Trade.objects.create(
            account=account, symbol=symbol, type=Trade.BUY,
            quantite=quantite, prix_exec=prix,
            montant_eur=montant_eur, frais=frais,
            solde_avant=solde_avant, solde_apres=account.solde,
        )
        return Response({
            "message":  f"Achat exécuté : {quantite} {symbol} @ {prix} €",
            "trade":    TradeSerializer(trade).data,
            "solde":    str(account.solde),
        }, status=201)

    @transaction.atomic
    def _sell(self, account, symbol, prix, quantite):
        try:
            position = Position.objects.get(account=account, symbol=symbol)
        except Position.DoesNotExist:
            return Response({"error": f"Vous ne détenez pas de {symbol}."}, status=400)

        if position.quantite < quantite:
            return Response({
                "error": f"Quantité insuffisante. Disponible : {position.quantite} {symbol}"
            }, status=400)

        montant_eur = (quantite * prix).quantize(Decimal("0.01"))
        frais       = (montant_eur * TAUX_FRAIS).quantize(Decimal("0.0001"))
        net_eur     = montant_eur - frais

        solde_avant    = account.solde
        account.solde += net_eur
        account.save()

        position.quantite   -= quantite
        position.prix_actuel = prix
        if position.quantite == 0:
            position.delete()
        else:
            position.save()

        trade = Trade.objects.create(
            account=account, symbol=symbol, type=Trade.SELL,
            quantite=quantite, prix_exec=prix,
            montant_eur=montant_eur, frais=frais,
            solde_avant=solde_avant, solde_apres=account.solde,
        )
        return Response({
            "message": f"Vente exécutée : {quantite} {symbol} @ {prix} €",
            "trade":   TradeSerializer(trade).data,
            "solde":   str(account.solde),
        }, status=201)


class TradeHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = TradeSerializer

    def get_queryset(self):
        account_id = self.kwargs["account_id"]
        account    = get_or_check_account(self.request, account_id)
        if not account:
            return Trade.objects.none()
        return account.trades.all()[:100]


class LeaderboardView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class   = LeaderboardSerializer
    queryset           = LeaderboardEntry.objects.select_related(
        "account__user"
    ).order_by("rang")[:50]