# main/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import escape
from .models import Profile, WallPost, WallComment
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
import bleach


class UserRegisterForm(UserCreationForm):
    """Форма регистрации с валидацией email."""
    email = forms.EmailField(
        required=True,
        label="Электронная почта",
        help_text="Введите корректный адрес email"
    )
    agree_terms = forms.BooleanField(
        required=True,
        label="Я принимаю Пользовательское соглашение"
    )
    agree_privacy = forms.BooleanField(
        required=True,
        label="Я принимаю Политику конфиденциальности"
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'agree_terms', 'agree_privacy']

    def clean_username(self):
        """Валидация имени пользователя."""
        username = self.cleaned_data.get('username')
        if len(username) < 3:
            raise ValidationError("Имя пользователя должно быть не менее 3 символов.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Пользователь с таким именем уже существует.")
        return username

    def clean_email(self):
        """Валидация email (должен быть уникальным)."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Пользователь с таким email уже зарегистрирован.")
        return email

    def clean_password1(self):
        """Дополнительная валидация пароля."""
        password1 = self.cleaned_data.get('password1')
        if password1 and len(password1) < 8:
            raise ValidationError("Пароль должен быть не менее 8 символов.")
        return password1


class ThreadForm(forms.Form):
    """Форма для создания новой темы с валидацией и санитизацией."""
    title = forms.CharField(
        max_length=200,
        min_length=5,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Название темы (минимум 5 символов)',
            'required': 'required'
        }),
        label="Заголовок темы"
    )
    text = forms.CharField(
        min_length=10,
        max_length=5000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Текст первого сообщения (минимум 10 символов)',
            'required': 'required'
        }),
        label="Текст сообщения"
    )

    def clean_title(self):
        """Очистить и валидировать заголовок."""
        title = self.cleaned_data.get('title', '').strip()
        # Санитизация: удалить опасные теги и скрипты
        title = bleach.clean(title, tags=[], strip=True)
        if not title or len(title) < 5:
            raise ValidationError("Заголовок должен содержать минимум 5 символов.")
        return title

    def clean_text(self):
        """Очистить и валидировать текст сообщения."""
        text = self.cleaned_data.get('text', '').strip()
        # Санитизация: разрешить базовые теги, удалить скрипты
        allowed_tags = ['p', 'br', 'b', 'i', 'strong', 'em', 'a', 'code', 'pre', 'blockquote']
        text = bleach.clean(text, tags=allowed_tags, strip=True)
        if not text or len(text) < 10:
            raise ValidationError("Текст должен содержать минимум 10 символов.")
        return text


class PostForm(forms.Form):
    """Форма для добавления нового сообщения."""
    text = forms.CharField(
        min_length=1,
        max_length=5000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Ваше сообщение...',
            'required': 'required'
        }),
        label="Сообщение",
        required=False
    )
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        label="Изображение (опционально)"
    )

    def clean(self):
        """Убедиться, что есть либо текст, либо изображение."""
        cleaned_data = super().clean()
        text = cleaned_data.get('text', '').strip()
        image = cleaned_data.get('image')
        
        if not text and not image:
            raise ValidationError("Сообщение должно содержать текст или изображение.")
        
        return cleaned_data

    def clean_text(self):
        """Санитизировать текст."""
        text = self.cleaned_data.get('text', '').strip()
        if text:
            allowed_tags = ['p', 'br', 'b', 'i', 'strong', 'em', 'a', 'code', 'pre', 'blockquote']
            text = bleach.clean(text, tags=allowed_tags, strip=True)
        return text


class AvatarForm(forms.ModelForm):
    """Форма для загрузки аватарки с валидацией."""
    class Meta:
        model = Profile
        fields = ['avatar']
        widgets = {
            'avatar': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'id': 'id_avatar'
            })
        }
        labels = {
            'avatar': 'Аватар (JPG, PNG, GIF. Макс. 5MB)'
        }

    def clean_avatar(self):
        """Валидация размера и формата аватарки."""
        avatar = self.cleaned_data.get('avatar')
        if avatar:
            # Проверка размера (максимум 5MB)
            if avatar.size > 5 * 1024 * 1024:
                raise ValidationError("Размер файла не должен превышать 5MB.")
            
            # Проверка расширения
            allowed_extensions = ['jpg', 'jpeg', 'png', 'gif']
            file_ext = avatar.name.split('.')[-1].lower()
            if file_ext not in allowed_extensions:
                raise ValidationError(f"Допустимые форматы: {', '.join(allowed_extensions)}")
        
        return avatar


class WallPostForm(forms.ModelForm):
    """Форма для записи на стене."""
    class Meta:
        model = WallPost
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Напишите что-нибудь...'
            })
        }

    def clean_body(self):
        body = (self.cleaned_data.get('body') or '').strip()
        body = bleach.clean(body, tags=[], strip=True)
        if not body:
            raise ValidationError("Текст не может быть пустым.")
        return body


class WallCommentForm(forms.ModelForm):
    """Форма для комментария на стене."""
    class Meta:
        model = WallComment
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Оставьте комментарий...'
            })
        }

    def clean_body(self):
        body = (self.cleaned_data.get('body') or '').strip()
        body = bleach.clean(body, tags=[], strip=True)
        if not body:
            raise ValidationError("Комментарий не может быть пустым.")
        return body