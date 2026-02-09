from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0004_rename_main_conve_last_me_b0e74b_idx_main_conver_last_me_04db79_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='WallPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField(verbose_name='Текст')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='authored_wall_posts', to=settings.AUTH_USER_MODEL, verbose_name='Автор')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wall_posts', to=settings.AUTH_USER_MODEL, verbose_name='Владелец стены')),
            ],
            options={
                'verbose_name': 'Запись стены',
                'verbose_name_plural': 'Записи стены',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='WallComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField(verbose_name='Текст')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wall_comments', to=settings.AUTH_USER_MODEL, verbose_name='Автор')),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='main.wallpost', verbose_name='Запись')),
            ],
            options={
                'verbose_name': 'Комментарий стены',
                'verbose_name_plural': 'Комментарии стены',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='wallpost',
            index=models.Index(fields=['owner', '-created_at'], name='main_wallpo_owner_i_f52aa0_idx'),
        ),
        migrations.AddIndex(
            model_name='wallpost',
            index=models.Index(fields=['author'], name='main_wallpo_author__113f61_idx'),
        ),
        migrations.AddIndex(
            model_name='wallcomment',
            index=models.Index(fields=['post', 'created_at'], name='main_wallco_post_id_4b5e29_idx'),
        ),
        migrations.AddIndex(
            model_name='wallcomment',
            index=models.Index(fields=['author'], name='main_wallco_author__1c57b3_idx'),
        ),
    ]
