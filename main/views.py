from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit
import logging

from .models import Section, Subsection, Thread, Post, Profile
from .forms import ThreadForm, AvatarForm, UserRegisterForm

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect('section_list')

    form = UserRegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Аккаунт {username} успешно создан. Войдите, пожалуйста.')
            return redirect('login')
        except IntegrityError:
            logger.exception('Registration error')
            messages.error(request, 'Ошибка при создании аккаунта. Попробуйте ещё раз.')

    return render(request, 'main/register.html', {'form': form})


@login_required
@require_http_methods(["GET", "POST"])
def update_avatar(request):
    profile = request.user.profile
    form = AvatarForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, 'Аватар успешно обновлён.')
            return redirect('user_profile', user_id=request.user.id)
        except Exception:
            logger.exception('Avatar save error')
            messages.error(request, 'Ошибка при загрузке аватара. Попробуйте ещё раз.')

    return render(request, 'main/update_avatar.html', {'form': form})


def user_profile(request, user_id):
    user = get_object_or_404(User, id=user_id)
    post_count = user.posts.count()
    thread_count = user.threads.count()
    return render(request, 'main/user_profile.html', {
        'profile_user': user,
        'post_count': post_count,
        'thread_count': thread_count,
    })


def section_list(request):
    sections = Section.objects.prefetch_related('subsections').all()

    pinned_threads = Thread.objects.select_related('author', 'subsection__section')\
        .filter(is_pinned=True).order_by('-created_at')[:10]

    latest_threads = Thread.objects.select_related('author', 'subsection__section')\
        .filter(is_pinned=False).order_by('-created_at')[:10]

    stats = {
        'users': User.objects.count(),
        'threads': Thread.objects.count(),
        'posts': Post.objects.count(),
    }

    return render(request, 'main/section_list.html', {
        'sections': sections,
        'pinned_threads': pinned_threads,
        'latest_threads': latest_threads,
        'stats': stats,
    })


def thread_list(request, subsection_id):
    subsection = get_object_or_404(Subsection, id=subsection_id)
    order = request.GET.get('order', 'latest')

    if order == 'active':
        queryset = subsection.threads.select_related('author').order_by('-last_reply_at')
    else:
        queryset = subsection.threads.select_related('author').order_by('-created_at')

    paginator = Paginator(queryset, 25)
    page_number = request.GET.get('page')
    threads = paginator.get_page(page_number)

    return render(request, 'main/thread_list.html', {
        'subsection': subsection,
        'threads': threads,
        'current_order': order,
    })


def post_list(request, thread_id):
    thread = get_object_or_404(Thread, id=thread_id)

    # increment views once per session
    viewed = request.session.setdefault('viewed_threads', [])
    if thread_id not in viewed:
        try:
            thread.increment_views()
        except Exception:
            logger.exception('Failed to increment views')
        viewed.append(thread_id)
        request.session.modified = True

    posts_qs = thread.posts.select_related('author', 'author__profile').all()
    paginator = Paginator(posts_qs, 10)
    posts = paginator.get_page(request.GET.get('page'))

    return render(request, 'main/post_list.html', {'thread': thread, 'posts': posts})


@staff_member_required
@require_http_methods(['POST'])
def toggle_pin_thread(request, thread_id):
    thread = get_object_or_404(Thread, id=thread_id)
    thread.is_pinned = not thread.is_pinned
    thread.save(update_fields=['is_pinned'])
    status = 'закреплена' if thread.is_pinned else 'откреплена'
    messages.success(request, f'Тема «{thread.title}» {status}.')
    return redirect('post_list', thread_id=thread.id)


@login_required
@ratelimit(key='user', rate='10/h', method='POST')
@require_http_methods(['GET', 'POST'])
def new_thread(request, subsection_id):
    subsection = get_object_or_404(Subsection, id=subsection_id)
    form = ThreadForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                thread = Thread.objects.create(
                    title=form.cleaned_data['title'],
                    author=request.user,
                    subsection=subsection,
                    last_reply_at=timezone.now()
                )
                Post.objects.create(
                    text=form.cleaned_data['text'],
                    author=request.user,
                    thread=thread
                )
            messages.success(request, 'Тема успешно создана.')
            return redirect('post_list', thread_id=thread.id)
        except Exception:
            logger.exception('Create thread error')
            messages.error(request, 'Ошибка при создании темы. Попробуйте ещё раз.')

    return render(request, 'main/new_thread.html', {'form': form, 'subsection': subsection})


@login_required
@ratelimit(key='user', rate='30/h', method='POST')
@require_http_methods(['POST'])
def new_post(request, thread_id):
    thread = get_object_or_404(Thread, id=thread_id)
    text = request.POST.get('text', '').strip()
    image = request.FILES.get('image')
    if not text and not image:
        messages.error(request, 'Сообщение не может быть пустым.')
        return redirect('post_list', thread_id=thread_id)

    try:
        Post.objects.create(text=text, image=image, author=request.user, thread=thread)
        thread.last_reply_at = timezone.now()
        thread.save(update_fields=['last_reply_at'])
        messages.success(request, 'Сообщение добавлено.')
    except Exception:
        logger.exception('Create post error')
        messages.error(request, 'Ошибка при добавлении сообщения.')

    return redirect('post_list', thread_id=thread_id)


@login_required
@require_http_methods(['GET', 'POST'])
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if post.author != request.user:
        messages.error(request, 'Вы не можете редактировать чужой пост.')
        return redirect('post_list', thread_id=post.thread.id)

    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        if not text:
            messages.error(request, 'Текст сообщения не может быть пустым.')
            return redirect('post_list', thread_id=post.thread.id)
        post.text = text
        post.save(update_fields=['text', 'updated_at'])
        messages.success(request, 'Сообщение обновлено.')
        return redirect('post_list', thread_id=post.thread.id)

    return render(request, 'main/edit_post.html', {'post': post})


@login_required
def choose_subsection(request):
    sections = Section.objects.prefetch_related('subsections').all()
    return render(request, 'main/choose_subsection.html', {'sections': sections})


# ==============================================================================
# АВАТАРКИ — управление изображением профиля пользователя

@login_required
@require_http_methods(["GET", "POST"])
def update_avatar(request):
    """
    Страница изменения аватарки текущего пользователя.
    Создаёт профиль, если он не существует.
    """
    # Создаём профиль, если его нет
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = AvatarForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Аватар успешно обновлён.")
                return redirect('user_profile', user_id=request.user.id)
            except Exception as e:
                logger.error(f"Ошибка при сохранении аватара для {request.user.username}: {e}")
                messages.error(request, "Ошибка при загрузке аватара. Попробуйте ещё раз.")
    else:
        form = AvatarForm(instance=profile)
    
    return render(request, 'main/update_avatar.html', {'form': form})



# ==============================================================================
# ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ

def user_profile(request, user_id):
    """
    Отображает публичный профиль пользователя:
    - имя, дата регистрации
    - количество сообщений и созданных тем
    """
    user = get_object_or_404(User, id=user_id)
    post_count = user.posts.count()
    thread_count = user.threads.count()
    return render(request, 'main/user_profile.html', {
        'profile_user': user,
        'post_count': post_count,
        'thread_count': thread_count,
    })


# ==============================================================================
# ГЛАВНАЯ СТРАНИЦА — список разделов и статистика

def section_list(request):
    """
    Главная страница форума.
    Отображает:
      - все разделы и подразделы
      - закреплённые темы (из любого подраздела)
      - последние активные темы
      - общую статистику (пользователи, темы, посты)
    """
    sections = Section.objects.prefetch_related('subsections').all()
    
    # Закреплённые темы (из всех подразделов)
    pinned_threads = Thread.objects.select_related(
        'author', 'subsection__section'
    ).filter(is_pinned=True).order_by('-created_at')
    
    # Последние 10 обычных тем
    latest_threads = Thread.objects.select_related(
        'author', 'subsection__section'
    ).filter(is_pinned=False).order_by('-created_at')[:10]

    # Общая статистика
    stats = {
        'users': User.objects.count(),
        'threads': Thread.objects.count(),
        'posts': Post.objects.count(),
    }
    return render(request, 'main/section_list.html', {
        'sections': sections,
        'pinned_threads': pinned_threads,
        'latest_threads': latest_threads,
        'stats': stats,
    })


# ==============================================================================
# ТЕМЫ В ПОДРАЗДЕЛЕ

def thread_list(request, subsection_id):
    """
    Список тем в конкретном подразделе.
    Поддерживает сортировку:
      - ?order=latest (по умолчанию)
      - ?order=active (по дате последнего ответа)
    """
    subsection = get_object_or_404(Subsection, id=subsection_id)
    order = request.GET.get('order', 'latest')

    if order == 'active':
        threads = subsection.threads.order_by('-last_reply_at')
        order_label = "По последнему ответу"
    else:
        threads = subsection.threads.order_by('-created_at')
        order_label = "Последние темы"

    return render(request, 'main/thread_list.html', {
        'subsection': subsection,
        'threads': threads,
        'current_order': order,
        'order_label': order_label,
    })


# ==============================================================================
# СООБЩЕНИЯ В ТЕМЕ (с пагинацией)

def post_list(request, thread_id):
    """
    Отображает все сообщения в теме с пагинацией (10 постов на страницу).
    Использует select_related для оптимизации запросов к автору и его профилю.
    """
    thread = get_object_or_404(Thread, id=thread_id)
    posts_list = thread.posts.select_related(
        'author', 'author__profile'  # ← важно для отображения аватарок!
    ).all()
    
    paginator = Paginator(posts_list, 10)
    page_number = request.GET.get('page')
    posts = paginator.get_page(page_number)
    
    return render(request, 'main/post_list.html', {
        'thread': thread,
        'posts': posts,
    })


# ==============================================================================
# УПРАВЛЕНИЕ ТЕМОЙ (закрепление/открепление)

@staff_member_required
def toggle_pin_thread(request, thread_id):
    """
    Закрепляет или открепляет тему (только для персонала).
    После действия — перенаправляет обратно в тему.
    """
    thread = get_object_or_404(Thread, id=thread_id)
    thread.is_pinned = not thread.is_pinned
    thread.save(update_fields=['is_pinned'])
    
    status = "закреплена" if thread.is_pinned else "откреплена"
    messages.success(request, f"Тема «{thread.title}» успешно {status}.")
    return redirect('post_list', thread_id=thread.id)


# ==============================================================================
# СОЗДАНИЕ НОВОЙ ТЕМЫ

@login_required
def new_thread(request, subsection_id):
    """
    Создание новой темы в указанном подразделе.
    Первое сообщение создаётся одновременно с темой.
    """
    subsection = get_object_or_404(Subsection, id=subsection_id)
    if request.method == 'POST':
        form = ThreadForm(request.POST)
        if form.is_valid():
            thread = Thread.objects.create(
                title=form.cleaned_data['title'],
                author=request.user,
                subsection=subsection,
                last_reply_at=timezone.now()
            )
            Post.objects.create(
                text=form.cleaned_data['text'],
                author=request.user,
                thread=thread
            )
            return redirect('post_list', thread_id=thread.id)
    else:
        form = ThreadForm()
    return render(request, 'main/new_thread.html', {
        'form': form,
        'subsection': subsection
    })


# ==============================================================================
# ДОБАВЛЕНИЕ НОВОГО СООБЩЕНИЯ В ТЕМУ

@login_required
def new_post(request, thread_id):
    """
    Добавление нового сообщения в существующую тему.
    Поддерживается текст и изображение.
    Обновляет last_reply_at у темы.
    """
    thread = get_object_or_404(Thread, id=thread_id)
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        image = request.FILES.get('image')
        if text or image:
            Post.objects.create(
                text=text,
                image=image,
                author=request.user,
                thread=thread
            )
            thread.last_reply_at = timezone.now()
            thread.save(update_fields=['last_reply_at'])
            messages.success(request, "Сообщение добавлено.")
        else:
            messages.error(request, "Сообщение не может быть пустым.")
    return redirect('post_list', thread_id=thread.id)


# ==============================================================================
# РЕДАКТИРОВАНИЕ СООБЩЕНИЯ

@login_required
def edit_post(request, post_id):
    """
    Редактирование своего сообщения.
    Доступно только автору поста.
    """
    post = get_object_or_404(Post, id=post_id)
    if post.author != request.user:
        messages.error(request, "Вы не можете редактировать чужой пост.")
        return redirect('post_list', thread_id=post.thread.id)
    
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        if text:
            post.text = text
            post.save()
            messages.success(request, "Сообщение обновлено.")
            return redirect('post_list', thread_id=post.thread.id)
    
    return render(request, 'main/edit_post.html', {'post': post})


# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ СТРАНИЦЫ

@login_required
def choose_subsection(request):
    """
    Выбор подраздела при создании новой темы (если не указан напрямую).
    """
    sections = Section.objects.prefetch_related('subsections').all()
    return render(request, 'main/choose_subsection.html', {'sections': sections})