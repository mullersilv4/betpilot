from django.contrib.auth import views as auth_views
from django.urls import path
from django.urls import reverse_lazy

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('login/', views.DashboardLoginView.as_view(), name='login'),
    path('cadastro/', views.signup, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path(
        'recuperar-senha/',
        auth_views.PasswordResetView.as_view(
            template_name='dashboard/auth/password_reset_form.html',
            email_template_name='dashboard/auth/password_reset_email.html',
            subject_template_name='dashboard/auth/password_reset_subject.txt',
            success_url=reverse_lazy('dashboard:password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'recuperar-senha/enviado/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='dashboard/auth/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'recuperar-senha/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='dashboard/auth/password_reset_confirm.html',
            success_url=reverse_lazy('dashboard:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'recuperar-senha/concluido/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='dashboard/auth/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path('api/jogos/', views.event_autocomplete, name='event_autocomplete'),
    path('', views.index, name='index'),
    path('entidades/<int:pk>/excluir/', views.delete_entity, name='delete_entity'),
    path('apostas/<int:pk>/editar/', views.edit_bet, name='edit_bet'),
    path('apostas/<int:pk>/finalizar-surebet/', views.settle_surebet, name='settle_surebet'),
    path('apostas/<int:pk>/status/<str:status>/', views.settle_bet, name='settle_bet'),
    path('apostas/<int:pk>/excluir/', views.delete_bet, name='delete_bet'),
    path('bancas/<int:pk>/', views.bankroll_detail, name='bankroll_detail'),
    path('bancas/<int:pk>/editar/', views.edit_bankroll, name='edit_bankroll'),
    path('bancas/<int:pk>/excluir/', views.delete_bankroll, name='delete_bankroll'),
]
