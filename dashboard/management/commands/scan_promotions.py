from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from dashboard.promotion_scan import scan_user_promotion_pages


class Command(BaseCommand):
    help = 'Varre páginas públicas cadastradas e cria promoções detectadas para revisão.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='Usuário dono das páginas cadastradas.')
        parser.add_argument('--limit', type=int, default=0, help='Limite opcional de páginas.')
        parser.add_argument('--timeout', type=int, default=8, help='Timeout por página em segundos.')

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options['username'])
        except User.DoesNotExist as exc:
            raise CommandError(f'Usuário não encontrado: {options["username"]}') from exc

        result = scan_user_promotion_pages(
            user,
            limit=options['limit'] or None,
            timeout=options['timeout'],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Páginas: {result["pages"]}; trechos: {result["matches"]}; '
                f'promoções criadas: {result["created"]}; atualizadas: {result["updated"]}.'
            )
        )
        for error in result['errors']:
            self.stdout.write(self.style.WARNING(error))
