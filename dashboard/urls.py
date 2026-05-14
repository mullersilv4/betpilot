from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('login/', views.DashboardLoginView.as_view(), name='login'),
    path('cadastro/', views.signup, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.index, name='index'),
    path('apostas/<int:pk>/editar/', views.edit_bet, name='edit_bet'),
    path('apostas/<int:pk>/status/<str:status>/', views.settle_bet, name='settle_bet'),
    path('apostas/<int:pk>/excluir/', views.delete_bet, name='delete_bet'),
    path('bancas/<int:pk>/', views.bankroll_detail, name='bankroll_detail'),
    path('bancas/<int:pk>/editar/', views.edit_bankroll, name='edit_bankroll'),
]
