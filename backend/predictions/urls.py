from django.urls import path
from . import views

urlpatterns = [
    path('predict/<str:symbol>/',           views.PredictView.as_view()),
    path('models/<str:symbol>/metrics/',    views.ModelMetricsView.as_view()),
    path('prices/<str:symbol>/',            views.PricesView.as_view()),
    path('train/',                          views.TrainView.as_view()),
    path("train/history/",                  views.TrainingHistoryView.as_view()), 
    path('train/<int:job_id>/',             views.TrainingJobDetailView.as_view()), 
    path('train/<str:task_id>/status/',     views.TrainStatusView.as_view()),
    path("admin/data/",                     views.AdminDataView.as_view()),
    path("admin/data/<str:symbol>/",        views.AdminSymbolDataView.as_view()),
    path("prices/live/<str:symbol>/",       views.LivePriceView.as_view()),
]