from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.templatetags.static import static
from django.urls import reverse
from django.core.validators import FileExtensionValidator
from PIL import Image
import logging

logger = logging.getLogger(__name__)

DEFAULT_AVATAR_NAME = 'avatars/default.png'


class Section(models.Model):
    """Главный раздел форума."""
    title = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,  # Индекс для быстрого поиска
        verbose_name="Название"
    )
    description = models.TextField(blank=True, verbose_name="Описание")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Раздел'
        verbose_name_plural = 'Разделы'
        indexes = [
            models.Index(fields=['order', 'title']),
        ]

    def __str__(self):
        return self.title


class Profile(models.Model):
    """Профиль пользователя с аватаром."""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name="Пользователь"
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        default='avatars/default.png',
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])],
        verbose_name="Аватар",
        help_text="Максимальный размер: 5MB. Рекомендуемые размеры: 300x300px"
    )
    bio = models.TextField(blank=True, max_length=500, verbose_name="О себе")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'
        indexes = [
            models.Index(fields=['user']),
        ]

    def get_absolute_url(self):
        return reverse('profile', args=[self.user.username])

    def __str__(self):
        return f'{self.user.username} Profile'

    @property
    def avatar_url(self):
        if not self.avatar or self.avatar.name == DEFAULT_AVATAR_NAME:
            return static('images/default-avatar.png')
        return self.avatar.url

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.avatar and self.avatar.name != 'avatars/default.png':
            try:
                img = Image.open(self.avatar.path)
                if img.height > 300 or img.width > 300:
                    output_size = (300, 300)
                    img.thumbnail(output_size)
                    img.save(self.avatar.path)
            except Exception as e:
                logger.error(f"Ошибка при обработке аватара для {self.user.username}: {e}")


class Subsection(models.Model):
    """Подраздел форума (принадлежит разделу)."""
    title = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name="Название"
    )
    description = models.TextField(blank=True, verbose_name="Описание")
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='subsections',
        verbose_name="Раздел"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Подраздел'
        verbose_name_plural = 'Подразделы'
        unique_together = ('section', 'title')  # Уникальное название в пределах раздела
        indexes = [
            models.Index(fields=['section', 'order']),
        ]

    def __str__(self):
        return self.title


class Thread(models.Model):
    """Тема (обсуждение) в подразделе."""
    title = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name="Заголовок"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='threads',
        verbose_name="Автор"
    )
    subsection = models.ForeignKey(
        Subsection,
        on_delete=models.CASCADE,
        related_name='threads',
        verbose_name="Подраздел"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания", db_index=True)
    last_reply_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Дата последнего ответа",
        db_index=True
    )
    is_pinned = models.BooleanField(
        default=False,
        verbose_name="Закреплена",
        db_index=True
    )
    views_count = models.PositiveIntegerField(default=0, verbose_name="Просмотры")

    class Meta:
        ordering = ['-is_pinned', '-last_reply_at']
        verbose_name = 'Тема'
        verbose_name_plural = 'Темы'
        indexes = [
            models.Index(fields=['subsection', '-is_pinned', '-last_reply_at']),
            models.Index(fields=['author']),
        ]

    def __str__(self):
        return self.title

    def increment_views(self):
        """Увеличить счётчик просмотров."""
        self.views_count = models.F('views_count') + 1
        self.save(update_fields=['views_count'])


class Post(models.Model):
    """Сообщение (ответ) в теме."""
    text = models.TextField(verbose_name="Текст", blank=False)
    image = models.ImageField(
        upload_to='posts/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])],
        verbose_name="Изображение",
        help_text="Опционально. Максимальный размер: 10MB"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='posts',
        verbose_name="Автор"
    )
    thread = models.ForeignKey(
        Thread,
        on_delete=models.CASCADE,
        related_name='posts',
        verbose_name="Тема"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания", db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата редактирования")

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        indexes = [
            models.Index(fields=['thread', 'created_at']),
            models.Index(fields=['author']),
        ]

    def __str__(self):
        return f'Post by {self.author.username} in {self.thread.title}'


class Conversation(models.Model):
    """Диалог 1-на-1 между пользователями."""
    participants = models.ManyToManyField(
        User,
        related_name='conversations',
        verbose_name="Участники"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    last_message_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата последнего сообщения")

    class Meta:
        ordering = ['-last_message_at', '-updated_at']
        verbose_name = 'Диалог'
        verbose_name_plural = 'Диалоги'
        indexes = [
            models.Index(fields=['-last_message_at']),
        ]

    def __str__(self):
        return f"Conversation {self.id}"


class Message(models.Model):
    """Личное сообщение в диалоге."""
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name="Диалог"
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name="Отправитель"
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_messages',
        verbose_name="Получатель"
    )
    body = models.TextField(verbose_name="Текст")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отправки")
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")
    read_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата прочтения")

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f"Message {self.id}"


class TypingStatus(models.Model):
    """Кратковременный индикатор набора текста в диалоге."""
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='typing_statuses',
        verbose_name="Диалог"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='typing_statuses',
        verbose_name="Пользователь"
    )
    updated_at = models.DateTimeField(default=timezone.now, verbose_name="Время набора")

    class Meta:
        verbose_name = 'Статус набора'
        verbose_name_plural = 'Статусы набора'
        unique_together = ('conversation', 'user')
        indexes = [
            models.Index(fields=['conversation', 'updated_at']),
        ]

    def __str__(self):
        return f"Typing {self.user_id} in {self.conversation_id}"