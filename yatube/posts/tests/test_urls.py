from http import HTTPStatus
from urllib.parse import urljoin
from django.core.cache import cache
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.test import TestCase, Client

from ..models import Post, Group


User = get_user_model()


class StaticUrlTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author = User.objects.create_user(username='author', id=1)
        cls.group = Group.objects.create(
            title='test-group',
            slug='test-slug',
        )
        cls.post = Post.objects.create(
            author=cls.author,
            text='Тестовый пост',
        )

    def setUp(self):
        cache.clear()
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_author = Client()
        self.user = User.objects.create_user(username='guest')
        self.authorized_client.force_login(self.user)
        self.authorized_author.force_login(self.author)

    def test_url_for_authorized(self):
        """Страница /create/ доступна авторизованному пользователю"""
        response = self.authorized_client.get('/create/')
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_private_url(self):
        """Без авторизации приватные URL недоступны"""
        url_names = (
            '/create/',
            '/posts/1/edit/',
            '/admin/',
        )
        for url_name in url_names:
            with self.subTest(url_name=url_name):
                response = self.guest_client.get(url_name)
                self.assertEqual(response.status_code, HTTPStatus.FOUND)

    def test_redirect_not_authorized_on_login(self):
        """Страница /create/ перенаправит гостя
           на страницу входа
        """
        response = self.guest_client.get(reverse('posts:post_create'))
        url = urljoin(reverse('users:login'), "?next=/create/")
        self.assertRedirects(response, url)

    def test_url_exists_for_all(self):
        """Страницы /, group, profile, posts доступны любому пользователю"""
        pages = ('/', '/group/test-slug/', '/profile/guest/', '/posts/1/',)
        for page in pages:
            with self.subTest():
                response = self.guest_client.get(page)
                self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_url_for_authorized_author(self):
        """Страница /posts/<>/edit/ доступна только автору"""
        response = self.authorized_author.get('/posts/1/edit/')
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_urls_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_url_names = {
            '/': 'posts/index.html',
            '/group/test-slug/': 'posts/group_list.html',
            '/profile/guest/': 'posts/profile.html',
            '/posts/1/': 'posts/post_detail.html',
            '/posts/1/edit/': 'posts/create_post.html',
            '/create/': 'posts/create_post.html',
        }
        for url, template in templates_url_names.items():
            with self.subTest(url=url):
                response = self.authorized_author.get(url)
                self.assertTemplateUsed(response, template)

    def test_page_404(self):
        response = self.guest_client.get('/unexisting_page/')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
