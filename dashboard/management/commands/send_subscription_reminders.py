from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone

from dashboard.models import SubscriptionReminder
from dashboard.models import UserAccess


REMINDER_DAYS = {7, 3, 1}


class Command(BaseCommand):
    help = 'Envia lembretes de renovação para assinaturas próximas do vencimento.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra os lembretes elegíveis sem enviar e-mail nem registrar no banco.',
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        dry_run = options['dry_run']
        candidates = UserAccess.objects.filter(
            status=UserAccess.Status.ACTIVE,
            subscription_ends_at__isnull=False,
        ).select_related('user')
        sent_count = 0
        skipped_count = 0

        for access in candidates:
            expiration_date = timezone.localtime(access.subscription_ends_at).date()
            days_before = (expiration_date - today).days
            if days_before not in REMINDER_DAYS:
                continue
            if not access.user.email:
                skipped_count += 1
                self.stderr.write(f'{access.user}: sem e-mail cadastrado.')
                continue
            if SubscriptionReminder.objects.filter(access=access, days_before=days_before).exists():
                skipped_count += 1
                continue

            renew_url = f'{settings.FREEBETAR_SITE_URL}/assinatura/'
            subject = f'Freebetar: sua assinatura vence em {days_before} dia(s)'
            message = (
                f'Olá, {access.user.get_full_name() or access.user.username}!\n\n'
                f'Sua assinatura do Freebetar vence em {days_before} dia(s), no dia '
                f'{expiration_date.strftime("%d/%m/%Y")}.\n\n'
                f'Para manter o acesso, renove seu plano aqui:\n{renew_url}\n\n'
                'Se você já renovou, pode desconsiderar esta mensagem.\n\n'
                'Equipe Freebetar'
            )
            if dry_run:
                self.stdout.write(f'[dry-run] {access.user.email}: {days_before} dia(s)')
                sent_count += 1
                continue

            try:
                reminder = SubscriptionReminder.objects.create(access=access, days_before=days_before)
            except IntegrityError:
                skipped_count += 1
                continue

            try:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [access.user.email], fail_silently=False)
            except Exception:
                reminder.delete()
                raise
            sent_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'Lembretes enviados: {sent_count}. Ignorados: {skipped_count}.')
        )
