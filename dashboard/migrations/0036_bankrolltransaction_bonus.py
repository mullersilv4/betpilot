from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0035_userpreference_tutorials_seen_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bankrolltransaction',
            name='kind',
            field=models.CharField(
                choices=[
                    ('deposit', 'Deposito'),
                    ('withdraw', 'Saque'),
                    ('adjustment', 'Ajuste'),
                    ('bonus', 'Bônus'),
                    ('transfer_in', 'Transferência entrada'),
                    ('transfer_out', 'Transferência saida'),
                ],
                max_length=16,
                verbose_name='tipo',
            ),
        ),
    ]
