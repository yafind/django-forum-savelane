from django.contrib import admin
from .models import Profile, Section, Subsection, Thread, Post, Conversation, Message, WallPost, WallComment

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'description')

@admin.register(Subsection)
class SubsectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'section', 'description')
    list_filter = ('section',)

@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'subsection', 'created_at')
    list_filter = ('subsection', 'created_at')
    search_fields = ('title', 'author__username')

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('author', 'thread', 'created_at', 'text_preview')
    list_filter = ('thread__subsection', 'created_at')
    search_fields = ('text', 'author__username')

    def text_preview(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Текст (предпросмотр)'

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'avatar']


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'last_message_at', 'updated_at')
    search_fields = ('id',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'recipient', 'created_at', 'is_read')
    list_filter = ('is_read', 'created_at')
    search_fields = ('body', 'sender__username', 'recipient__username')


@admin.register(WallPost)
class WallPostAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner', 'author', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('body', 'author__username', 'owner__username')


@admin.register(WallComment)
class WallCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'author', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('body', 'author__username')