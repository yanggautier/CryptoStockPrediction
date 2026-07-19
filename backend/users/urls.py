from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [

    # ── Auth
    path("auth/register/",        views.RegisterView.as_view()),
    path("auth/login/",           TokenObtainPairView.as_view()),
    path("auth/token/refresh/",   TokenRefreshView.as_view()),
    path("auth/me/",              views.MeView.as_view()),

    # ── Comptes virtuels
    path("accounts/",                     views.AccountListView.as_view()),
    path("accounts/<int:account_id>/",    views.AccountDetailView.as_view()),

    # ── Trading
    path("accounts/<int:account_id>/order/",   views.OrderView.as_view()),
    path("accounts/<int:account_id>/trades/",  views.TradeHistoryView.as_view()),

    # ── Leaderboard
    path("leaderboard/",  views.LeaderboardView.as_view()),
]