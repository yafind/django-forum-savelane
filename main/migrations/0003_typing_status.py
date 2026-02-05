from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_private_messages'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TypingStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('updated_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Время набора')),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='typing_statuses', to='main.conversation', verbose_name='Диалог')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='typing_statuses', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Статус набора',
                'verbose_name_plural': 'Статусы набора',
                'unique_together': {('conversation', 'user')},
            },
        ),
        migrations.AddIndex(
            model_name='typingstatus',
            index=models.Index(fields=['conversation', 'updated_at'], name='main_typin_convers_4b58c0_idx'),
        ),
    ]
