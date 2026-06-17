from django.contrib import messages
from django.shortcuts import redirect

from .models import ensure_user_access


class TrialAccessMiddleware:
    PUBLIC_PREFIXES = (
        '/vendas/',
        '/login/',
        '/cadastro/',
        '/logout/',
        '/assinatura/',
        '/recuperar-senha/',
        '/senha/',
        '/admin/',
        '/static/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self.should_check_access(request):
            access = ensure_user_access(request.user)
            if not access.has_access:
                messages.warning(
                    request,
                    'Seu teste gratuito de 7 dias terminou. Contrate um plano para continuar usando o Freebetar.',
                )
                return redirect('/vendas/#planos')

        return self.get_response(request)

    def should_check_access(self, request):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False

        path = request.path_info
        if path == '/vendas':
            return False
        return not any(path.startswith(prefix) for prefix in self.PUBLIC_PREFIXES)
