from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from dashboard.promotion_scan import scan_user_promotion_pages


class Command(BaseCommand):
    help = 'Varre paginas publicas cadastradas e cria promocoes detectadas para revisao.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='Usuario dono das paginas cadastradas.')
        parser.add_argument('--limit', type=int, default=0, help='Limite opcional de paginas.')
        parser.add_argument('--timeout', type=int, default=8, help='Timeout por pagina em segundos.')
        parser.add_argument(
            '--rendered',
            action='store_true',
            help='Tenta abrir a pagina com navegador headless antes do fallback HTML simples.',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options['username'])
        except User.DoesNotExist as exc:
            raise CommandError(f'Usuario nao encontrado: {options["username"]}') from exc

        result = scan_user_promotion_pages(
            user,
            limit=options['limit'] or None,
            timeout=options['timeout'],
            rendered=options['rendered'],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Paginas: {result["pages"]}; trechos: {result["matches"]}; '
                f'promocoes criadas: {result["created"]}; atualizadas: {result["updated"]}.'
            )
        )
        for error in result['errors']:
            self.stdout.write(self.style.WARNING(error))
