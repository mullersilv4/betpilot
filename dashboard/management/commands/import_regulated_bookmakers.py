from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from dashboard.bookmaker_import import import_regulated_csv


class Command(BaseCommand):
    help = 'Importa casas regulamentadas e cria aliases iniciais a partir de um CSV SPA.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', help='Caminho do CSV no formato empresa;cnpj;marca;dominio;status.')
        parser.add_argument('--username', required=True, help='Usuário dono dos cadastros.')
        parser.add_argument('--provider', default='the_odds_api', help='Nome do provedor dos aliases.')
        parser.add_argument('--no-aliases', action='store_true', help='Não criar aliases automaticamente.')

    def handle(self, *args, **options):
        csv_path = Path(options['csv_path'])
        if not csv_path.exists():
            raise CommandError(f'CSV não encontrado: {csv_path}')

        User = get_user_model()
        try:
            user = User.objects.get(username=options['username'])
        except User.DoesNotExist as exc:
            raise CommandError(f'Usuário não encontrado: {options["username"]}') from exc

        with csv_path.open('r', encoding='utf-8-sig', newline='') as file_obj:
            result = import_regulated_csv(
                file_obj,
                user,
                provider=options['provider'],
                create_aliases=not options['no_aliases'],
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Importadas: {result["imported"]}; atualizadas: {result["updated"]}; '
                f'aliases criados: {result["aliases_created"]}.'
            )
        )
        for error in result['errors']:
            self.stdout.write(self.style.WARNING(error))
