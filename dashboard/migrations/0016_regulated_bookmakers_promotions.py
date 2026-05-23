from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dashboard', '0015_surebetentry_freebet_trigger'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegulatedBookmaker',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(max_length=160, verbose_name='empresa')),
                ('brand', models.CharField(max_length=100, verbose_name='marca')),
                ('cnpj', models.CharField(blank=True, max_length=24, verbose_name='CNPJ')),
                ('domain', models.CharField(max_length=120, verbose_name='domínio oficial')),
                ('status', models.CharField(choices=[('authorized', 'Autorizada'), ('state', 'Estadual'), ('judicial_alert', 'Alerta judicial'), ('inactive', 'Inativa')], default='authorized', max_length=20, verbose_name='status')),
                ('source', models.CharField(blank=True, default='SPA/MF', max_length=120, verbose_name='origem')),
                ('judicial_alert', models.BooleanField(default=False, verbose_name='alerta judicial')),
                ('alert_note', models.CharField(blank=True, max_length=180, verbose_name='observação do alerta')),
                ('last_checked_at', models.DateTimeField(blank=True, null=True, verbose_name='última verificação')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='criada em')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regulated_bookmakers', to=settings.AUTH_USER_MODEL, verbose_name='usuário')),
            ],
            options={
                'verbose_name': 'casa regulamentada',
                'verbose_name_plural': 'casas regulamentadas',
                'ordering': ['brand', 'domain'],
                'unique_together': {('owner', 'domain')},
            },
        ),
        migrations.CreateModel(
            name='BookmakerAlias',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(default='the_odds_api', max_length=60, verbose_name='provedor')),
                ('alias', models.CharField(max_length=100, verbose_name='nome no provedor')),
                ('provider_key', models.CharField(blank=True, max_length=100, verbose_name='chave no provedor')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='criado em')),
                ('bookmaker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aliases', to='dashboard.regulatedbookmaker', verbose_name='casa regulamentada')),
            ],
            options={
                'verbose_name': 'alias de casa',
                'verbose_name_plural': 'aliases de casas',
                'ordering': ['provider', 'alias'],
                'unique_together': {('bookmaker', 'provider', 'alias')},
            },
        ),
        migrations.CreateModel(
            name='PromotionPage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(verbose_name='URL pública')),
                ('is_active', models.BooleanField(default=True, verbose_name='ativa')),
                ('last_scan_at', models.DateTimeField(blank=True, null=True, verbose_name='última varredura')),
                ('last_scan_note', models.CharField(blank=True, max_length=180, verbose_name='nota da última varredura')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='criada em')),
                ('bookmaker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='promotion_pages', to='dashboard.regulatedbookmaker', verbose_name='casa regulamentada')),
            ],
            options={
                'verbose_name': 'página de promoção',
                'verbose_name_plural': 'páginas de promoção',
                'ordering': ['bookmaker__brand', 'url'],
                'unique_together': {('bookmaker', 'url')},
            },
        ),
        migrations.CreateModel(
            name='Promotion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=160, verbose_name='título')),
                ('kind', models.CharField(choices=[('freebet', 'Freebet'), ('cashback', 'Cashback'), ('odds_boost', 'Odd turbinada'), ('bonus', 'Bônus')], default='freebet', max_length=16, verbose_name='tipo')),
                ('trigger', models.CharField(choices=[('lost', 'Se perder'), ('won', 'Se ganhar'), ('any', 'Ambas')], default='lost', max_length=8, verbose_name='quando gera')),
                ('freebet_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='valor da freebet')),
                ('min_odd', models.DecimalField(decimal_places=2, default=Decimal('1.01'), max_digits=8, verbose_name='odd mínima')),
                ('sport', models.CharField(blank=True, default='Futebol', max_length=60, verbose_name='esporte')),
                ('competition', models.CharField(blank=True, max_length=120, verbose_name='competição')),
                ('suggested_game', models.CharField(blank=True, max_length=160, verbose_name='jogo sugerido')),
                ('public_text', models.TextField(blank=True, verbose_name='texto público')),
                ('source_url', models.URLField(blank=True, verbose_name='URL da promoção')),
                ('is_active', models.BooleanField(default=True, verbose_name='ativa')),
                ('detected_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='detectada em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='atualizada em')),
                ('bookmaker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='promotions', to='dashboard.regulatedbookmaker', verbose_name='casa regulamentada')),
                ('page', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='promotions', to='dashboard.promotionpage', verbose_name='página')),
            ],
            options={
                'verbose_name': 'promoção',
                'verbose_name_plural': 'promoções',
                'ordering': ['-detected_at'],
            },
        ),
    ]
