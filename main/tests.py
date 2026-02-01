from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Section, Subsection, Thread, Post

class ForumTestCase(TestCase):
    def setUp(self):

        self.user = User.objects.create_user(username='testuser', password='12345')

        self.section = Section.objects.create(title='Тестовый раздел')
        self.subsection = Subsection.objects.create(
            title='Тестовый подраздел',
            section=self.section
        )
        self.thread = Thread.objects.create(
            title='Тестовая тема',
            author=self.user,
            subsection=self.subsection
        )

    def test_create_post_by_authenticated_user(self):
        """Авторизованный пользователь может создать пост"""
        self.client.login(username='testuser', password='12345')
        response = self.client.post(reverse('new_post', args=[self.thread.id]), {
            'text': 'Тестовый пост'
        })

        self.assertEqual(response.status_code, 302)

        self.assertEqual(Post.objects.count(), 1)
        self.assertEqual(Post.objects.first().text, 'Тестовый пост')

    def test_create_post_by_anonymous_user(self):
        """Анонимный пользователь не может создать пост"""
        response = self.client.post(reverse('new_post', args=[self.thread.id]), {
            'text': 'Пост от гостя'
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))
        self.assertEqual(Post.objects.count(), 0)