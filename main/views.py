from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count, OuterRef, Subquery, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit
import logging

from .models import Section, Subsection, Thread, Post, Profile, Conversation, Message, TypingStatus, WallPost, WallComment
from .emoji import render_emoji_html
from .forms import ThreadForm, AvatarForm, UserRegisterForm, WallPostForm, WallCommentForm

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
    wall_posts = WallPost.objects.filter(owner=user)
    wall_posts = wall_posts.select_related('author', 'owner').prefetch_related('comments__author')
    recent_posts = Post.objects.filter(author=user)
    recent_posts = recent_posts.select_related('thread', 'thread__subsection__section').order_by('-created_at')[:5]
    return render(request, 'main/user_profile.html', {
        'profile_user': user,
        'post_count': post_count,
        'thread_count': thread_count,
        'wall_posts': wall_posts,
        'recent_posts': recent_posts,
        'wall_form': WallPostForm() if request.user.is_authenticated else None,
        'wall_comment_form': WallCommentForm() if request.user.is_authenticated else None,
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
    wall_posts = WallPost.objects.filter(owner=user)
    wall_posts = wall_posts.select_related('author', 'owner').prefetch_related('comments__author')
    recent_posts = Post.objects.filter(author=user)
    recent_posts = recent_posts.select_related('thread', 'thread__subsection__section').order_by('-created_at')[:5]
    return render(request, 'main/user_profile.html', {
        'profile_user': user,
        'post_count': post_count,
        'thread_count': thread_count,
        'wall_posts': wall_posts,
        'recent_posts': recent_posts,
        'wall_form': WallPostForm() if request.user.is_authenticated else None,
        'wall_comment_form': WallCommentForm() if request.user.is_authenticated else None,
    })


@login_required
@require_http_methods(['POST'])
def wall_post_create(request, user_id):
    owner = get_object_or_404(User, id=user_id)
    form = WallPostForm(request.POST)
    if form.is_valid():
        WallPost.objects.create(owner=owner, author=request.user, body=form.cleaned_data['body'])
        messages.success(request, 'Запись добавлена.')
    else:
        messages.error(request, 'Не удалось добавить запись.')
    return redirect('user_profile', user_id=owner.id)


@login_required
@require_http_methods(['POST'])
def wall_comment_create(request, user_id, post_id):
    owner = get_object_or_404(User, id=user_id)
    post = get_object_or_404(WallPost, id=post_id, owner=owner)
    form = WallCommentForm(request.POST)
    if form.is_valid():
        WallComment.objects.create(post=post, author=request.user, body=form.cleaned_data['body'])
        messages.success(request, 'Комментарий добавлен.')
    else:
        messages.error(request, 'Не удалось добавить комментарий.')
    return redirect('user_profile', user_id=owner.id)


@login_required
@require_http_methods(['GET', 'POST'])
def wall_post_edit(request, user_id, post_id):
    owner = get_object_or_404(User, id=user_id)
    post = get_object_or_404(WallPost, id=post_id, owner=owner)
    if request.user != post.author and not request.user.is_staff:
        messages.error(request, 'Вы не можете редактировать эту запись.')
        return redirect('user_profile', user_id=owner.id)

    if request.method == 'POST':
        form = WallPostForm(request.POST, instance=post)
        if form.is_valid():
            form.save(update_fields=['body', 'updated_at'])
            messages.success(request, 'Запись обновлена.')
            return redirect('user_profile', user_id=owner.id)
    else:
        form = WallPostForm(instance=post)

    return render(request, 'main/wall_post_edit.html', {
        'profile_user': owner,
        'post': post,
        'form': form,
    })


@login_required
@require_http_methods(['POST'])
def wall_post_delete(request, user_id, post_id):
    owner = get_object_or_404(User, id=user_id)
    post = get_object_or_404(WallPost, id=post_id, owner=owner)
    if request.user != post.author and not request.user.is_staff:
        messages.error(request, 'Вы не можете удалить эту запись.')
        return redirect('user_profile', user_id=owner.id)
    post.delete()
    messages.success(request, 'Запись удалена.')
    return redirect('user_profile', user_id=owner.id)


@login_required
@require_http_methods(['GET', 'POST'])
def wall_comment_edit(request, user_id, post_id, comment_id):
    owner = get_object_or_404(User, id=user_id)
    post = get_object_or_404(WallPost, id=post_id, owner=owner)
    comment = get_object_or_404(WallComment, id=comment_id, post=post)
    if request.user != comment.author and not request.user.is_staff:
        messages.error(request, 'Вы не можете редактировать этот комментарий.')
        return redirect('user_profile', user_id=owner.id)

    if request.method == 'POST':
        form = WallCommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save(update_fields=['body', 'updated_at'])
            messages.success(request, 'Комментарий обновлён.')
            return redirect('user_profile', user_id=owner.id)
    else:
        form = WallCommentForm(instance=comment)

    return render(request, 'main/wall_comment_edit.html', {
        'profile_user': owner,
        'post': post,
        'comment': comment,
        'form': form,
    })


@login_required
@require_http_methods(['POST'])
def wall_comment_delete(request, user_id, post_id, comment_id):
    owner = get_object_or_404(User, id=user_id)
    post = get_object_or_404(WallPost, id=post_id, owner=owner)
    comment = get_object_or_404(WallComment, id=comment_id, post=post)
    if request.user != comment.author and not request.user.is_staff:
        messages.error(request, 'Вы не можете удалить этот комментарий.')
        return redirect('user_profile', user_id=owner.id)
    comment.delete()
    messages.success(request, 'Комментарий удалён.')
    return redirect('user_profile', user_id=owner.id)


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


# ==============================================================================
# ЛИЧНЫЕ СООБЩЕНИЯ

@login_required
def messages_list(request):
    conversation_items = _get_conversation_items(request.user)

    return render(request, 'main/messages_list.html', {
        'conversation_items': conversation_items,
    })


@login_required
@require_http_methods(["GET", "POST"])
def message_detail(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    other_user = conversation.participants.exclude(id=request.user.id).first()
    if not other_user:
        messages.error(request, 'Диалог недоступен.')
        return redirect('messages_list')

    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if not body:
            messages.error(request, 'Сообщение не может быть пустым.')
        else:
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                recipient=other_user,
                body=body
            )
            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=['last_message_at', 'updated_at'])
            return redirect('message_detail', conversation_id=conversation.id)

    Message.objects.filter(
        conversation=conversation,
        recipient=request.user,
        is_read=False
    ).update(is_read=True, read_at=timezone.now())

    message_list = conversation.messages.select_related('sender').all()

    conversation_items = _get_conversation_items(request.user)

    typing_cutoff = timezone.now() - timezone.timedelta(seconds=7)
    typing_active = TypingStatus.objects.filter(
        conversation=conversation,
        user=other_user,
        updated_at__gte=typing_cutoff
    ).exists()

    return render(request, 'main/message_detail.html', {
        'conversation': conversation,
        'other_user': other_user,
        'message_list': message_list,
        'conversation_items': conversation_items,
        'typing_active': typing_active,
    })


@login_required
def start_conversation(request, user_id):
    if request.user.id == user_id:
        messages.error(request, 'Нельзя писать самому себе.')
        return redirect('messages_list')

    other_user = get_object_or_404(User, id=user_id)

    existing = Conversation.objects.filter(participants=request.user).filter(
        participants=other_user
    ).annotate(participant_count=Count('participants')).filter(participant_count=2).first()

    if existing:
        return redirect('message_detail', conversation_id=existing.id)

    conversation = Conversation.objects.create()
    conversation.participants.add(request.user, other_user)
    return redirect('message_detail', conversation_id=conversation.id)


def _get_conversation_items(user):
    last_message_subquery = Message.objects.filter(
        conversation=OuterRef('pk')
    ).order_by('-created_at')

    conversations = Conversation.objects.filter(participants=user).annotate(
        unread_count=Count(
            'messages',
            filter=Q(messages__recipient=user, messages__is_read=False),
            distinct=True
        ),
        last_message_id=Subquery(last_message_subquery.values('id')[:1])
    ).prefetch_related('participants', 'participants__profile').order_by('-last_message_at', '-updated_at')

    last_message_ids = [c.last_message_id for c in conversations if c.last_message_id]
    last_messages = Message.objects.filter(id__in=last_message_ids).select_related('sender', 'recipient')
    last_message_map = {m.id: m for m in last_messages}

    typing_cutoff = timezone.now() - timezone.timedelta(seconds=7)
    typing_statuses = TypingStatus.objects.filter(
        conversation__in=conversations,
        updated_at__gte=typing_cutoff
    )
    typing_map = {(ts.conversation_id, ts.user_id): True for ts in typing_statuses}

    conversation_items = []
    for conversation in conversations:
        other_user = conversation.participants.exclude(id=user.id).first()
        is_typing = False
        if other_user:
            is_typing = typing_map.get((conversation.id, other_user.id), False)
        conversation_items.append({
            'conversation': conversation,
            'other_user': other_user,
            'last_message': last_message_map.get(conversation.last_message_id),
            'unread_count': conversation.unread_count,
            'is_typing': is_typing,
        })

    return conversation_items


@login_required
def messages_poll(request):
    conversation_items = _get_conversation_items(request.user)
    payload = []
    for item in conversation_items:
        last_message = item['last_message']
        other_user = item['other_user']
        payload.append({
            'conversation_id': item['conversation'].id,
            'other_user': {
                'id': other_user.id if other_user else None,
                'username': other_user.username if other_user else '',
                'avatar_url': other_user.profile.avatar_url if other_user else '',
            },
            'last_message': {
                'body': last_message.body if last_message else '',
                'body_html': render_emoji_html(last_message.body) if last_message else '',
                'created_at': last_message.created_at.isoformat() if last_message else '',
            },
            'unread_count': item['unread_count'],
            'is_typing': item['is_typing'],
        })

    return JsonResponse({'items': payload})


@login_required
@require_http_methods(["GET"])
def message_poll(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    other_user = conversation.participants.exclude(id=request.user.id).first()

    after = request.GET.get('after')
    message_qs = conversation.messages.select_related('sender').order_by('created_at')
    if after and after.isdigit():
        message_qs = message_qs.filter(id__gt=int(after))

    messages_payload = []
    for msg in message_qs:
        messages_payload.append({
            'id': msg.id,
            'sender_id': msg.sender_id,
            'sender_name': msg.sender.username,
            'created_at': msg.created_at.isoformat(),
            'body': msg.body,
            'body_html': render_emoji_html(msg.body),
        })

    typing_cutoff = timezone.now() - timezone.timedelta(seconds=7)
    typing_active = False
    if other_user:
        typing_active = TypingStatus.objects.filter(
            conversation=conversation,
            user=other_user,
            updated_at__gte=typing_cutoff
        ).exists()

    return JsonResponse({
        'messages': messages_payload,
        'typing_active': typing_active,
    })


@login_required
@require_http_methods(["POST"])
def typing_ping(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    TypingStatus.objects.update_or_create(
        conversation=conversation,
        user=request.user,
        defaults={'updated_at': timezone.now()}
    )
    return JsonResponse({'ok': True})