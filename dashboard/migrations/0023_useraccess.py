from datetime import timedelta

from django.conf import settings
from django.db import migrations
from django.db import models
import django.db.models.deletion
from django.utils import timezone


def create_trial_accesses(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0], settings.AUTH_USER_MODEL.split('.')[1])
    UserAccess = apps.get_model('dashboard', 'UserAccess')
    started_at = timezone.now()
    trial_ends_at = started_at + timedelta(days=7)

    for user in User.objects.all():
        UserAccess.objects.get_or_create(
            user_id=user.pk,
            defaults={
                'trial_started_at': started_at,
                'trial_ends_at': trial_ends_at,
                'status': 'trial',
                'created_at': started_at,
                'updated_at': started_at,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dashboard', '0022_monthlygoal_entity'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserAccess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('trial_started_at', models.DateTimeField(default=timezone.now, verbose_name='início do teste')),
                ('trial_ends_at', models.DateTimeField(verbose_name='fim do teste')),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('trial', 'Teste'),
                            ('active', 'Ativa'),
                            ('expired', 'Expirada'),
                            ('canceled', 'Cancelada'),
                        ],
                        default='trial',
                        max_length=20,
                        verbose_name='status',
                    ),
                ),
                ('subscription_ends_at', models.DateTimeField(blank=True, null=True, verbose_name='fim da assinatura')),
                ('created_at', models.DateTimeField(default=timezone.now, verbose_name='criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='atualizado em')),
                (
                    'user',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='access',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='usuário',
                    ),
                ),
            ],
            options={
                'verbose_name': 'acesso do usuário',
                'verbose_name_plural': 'acessos dos usuários',
            },
        ),
        migrations.RunPython(create_trial_accesses, migrations.RunPython.noop),
    ]
