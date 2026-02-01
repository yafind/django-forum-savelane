from django.urls import path
from . import views

urlpatterns = [
    path('', views.section_list, name='section_list'),
    path('subsection/<int:subsection_id>/', views.thread_list, name='thread_list'),
    path('thread/<int:thread_id>/', views.post_list, name='post_list'),
    path('thread/<int:thread_id>/new_post/', views.new_post, name='new_post'),
    path('post/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path('user/<int:user_id>/', views.user_profile, name='user_profile'),
    path('new-thread/', views.choose_subsection, name='choose_subsection'),
    path('subsection/<int:subsection_id>/new_thread/', views.new_thread, name='new_thread'),
    path('thread/<int:thread_id>/toggle-pin/', views.toggle_pin_thread, name='toggle_pin_thread'),
    path('avatar/', views.update_avatar, name='update_avatar'),
    path('register/', views.register, name='register')
]