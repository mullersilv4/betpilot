from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dashboard', '0019_alter_bookmakeralias_id_alter_promotion_id_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='freebet',
            name='source_bet',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='generated_freebets',
                to='dashboard.bet',
                verbose_name='aposta de origem',
            ),
        ),
        migrations.AddField(
            model_name='freebet',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='manual_freebets',
                to=settings.AUTH_USER_MODEL,
                verbose_name='usuário',
            ),
        ),
    ]
