from django.urls import path
from . import views

urlpatterns = [
    path('', views.section_list, name='section_list'),
    path('subsection/<int:subsection_id>/', views.thread_list, name='thread_list'),
    path('thread/<int:thread_id>/', views.post_list, name='post_list'),
    path('thread/<int:thread_id>/new_post/', views.new_post, name='new_post'),
    path('thread/<int:thread_id>/delete/', views.delete_thread, name='delete_thread'),
    path('post/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('user/<int:user_id>/', views.user_profile, name='user_profile'),
    path('user/<int:user_id>/wall/', views.wall_post_create, name='wall_post_create'),
    path('user/<int:user_id>/wall/<int:post_id>/edit/', views.wall_post_edit, name='wall_post_edit'),
    path('user/<int:user_id>/wall/<int:post_id>/delete/', views.wall_post_delete, name='wall_post_delete'),
    path('user/<int:user_id>/wall/<int:post_id>/comment/', views.wall_comment_create, name='wall_comment_create'),
    path('user/<int:user_id>/wall/<int:post_id>/comment/<int:comment_id>/edit/', views.wall_comment_edit, name='wall_comment_edit'),
    path('user/<int:user_id>/wall/<int:post_id>/comment/<int:comment_id>/delete/', views.wall_comment_delete, name='wall_comment_delete'),
    path('new-thread/', views.choose_subsection, name='choose_subsection'),
    path('subsection/<int:subsection_id>/new_thread/', views.new_thread, name='new_thread'),
    path('thread/<int:thread_id>/toggle-pin/', views.toggle_pin_thread, name='toggle_pin_thread'),
    path('avatar/', views.update_avatar, name='update_avatar'),
    path('register/', views.register, name='register'),
    path('rules/', views.rules, name='rules'),
    path('rules/user-agreement/', views.user_agreement, name='user_agreement'),
    path('rules/privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('messages/', views.messages_list, name='messages_list'),
    path('messages/poll/', views.messages_poll, name='messages_poll'),
    path('messages/start/<int:user_id>/', views.start_conversation, name='start_conversation'),
    path('messages/<int:conversation_id>/', views.message_detail, name='message_detail'),
    path('messages/<int:conversation_id>/poll/', views.message_poll, name='message_poll'),
    path('messages/<int:conversation_id>/typing/', views.typing_ping, name='typing_ping')
]