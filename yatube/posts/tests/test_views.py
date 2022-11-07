import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django import forms
from django.test import TestCase, Client, override_settings
from ..models import Post, Group, Follow

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)
User = get_user_model()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class TestPages(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author = User.objects.create_user(username='author')
        cls.guest = User.objects.create_user(username='guest')
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        cls.group = Group.objects.create(
            title='test-group',
            slug='test-slug',
        )
        cls.group_2 = Group.objects.create(
            title='test-group-2',
            slug='test-slug-2',
        )
        cls.post_1 = Post.objects.create(
            author=cls.author,
            group=cls.group,
            text='Тестовый пост',
            image=uploaded
        )
        cls.post_2 = Post.objects.create(
            author=cls.guest,
            group=cls.group_2,
            text='Тестовый пост 2',
            image=uploaded
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.guest_client = Client()
        self.authorized_author = Client()
        self.authorized_author.force_login(self.author)

    def check_context(self, response, page_obj, post_position):
        obj = response.context[page_obj][post_position]
        self.assertEqual(obj.author, self.author)
        self.assertEqual(obj.group, self.group)
        self.assertEqual(obj.text, 'Тестовый пост')
        self.assertEqual(obj.image, 'posts/small.gif')

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_list',
                    kwargs={'slug': 'test-slug'}): 'posts/group_list.html',
            reverse('posts:profile',
                    kwargs={'username': 'author'}): 'posts/profile.html',
            reverse('posts:post_detail',
                    kwargs={'post_id': self.post_1.id}):
            'posts/post_detail.html',
            reverse('posts:post_edit',
                    kwargs={'post_id': self.post_1.id}):
            'posts/create_post.html',
            reverse('posts:post_create'): 'posts/create_post.html',
        }
        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_author.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_index_page_show_correct_context(self):
        """Шаблон index.html сформирован с правильным контекстом"""
        response = self.authorized_author.get(reverse('posts:index'))
        self.check_context(response, 'page_obj', 1)

    def test_group_list_page_show_correct_context(self):
        """Шаблон group_list.html сформирован с правильным контекстом"""
        response = (self.authorized_author.
                    get(reverse('posts:group_list',
                        kwargs={'slug': 'test-slug'})))
        self.assertEqual(response.context.get('group').title, self.group.title)
        self.assertEqual(response.context.get('group').slug, self.group.slug)
        self.check_context(response, 'page_obj', 0)

    def test_profile_page_show_correct_context(self):
        """Шаблон profile.html сформирован с правильным контекстом"""
        response = (self.authorized_author.
                    get(reverse('posts:profile',
                        kwargs={'username': 'author'})))
        self.assertEqual(response.context.get('author').username,
                         self.author.username)
        self.assertEqual(response.context.get('count_posts'),
                         Post.objects.filter(author=self.author.id).count())
        self.check_context(response, 'page_obj', 0)

    def test_post_detail_page_show_correct_context(self):
        """Шаблон post_detail.html сформирован с правильным контекстом"""
        response = (self.guest_client.
                    get(reverse('posts:post_detail',
                        kwargs={'post_id': '2'})))
        self.assertEqual(response.context.get('image'), self.post_2.image)
        self.assertEqual(response.context.get('post_id'), self.post_2.id)
        self.assertEqual(response.context.get('count_posts'),
                         Post.objects.filter(id=self.post_2.id).count())

    def test_create_post_page_show_correct_context(self):
        """Шаблон create_post.html сформирован с правильным контекстом"""
        response = self.authorized_author.get(reverse('posts:post_create'))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_edit_post_page_show_correct_context(self):
        """Шаблон create_post.html для post_edit сформирован с правильным
           контекстом"""
        response = (self.authorized_author.
                    get(reverse('posts:post_edit',
                        kwargs={'post_id': '1'})))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)
        self.assertEqual(response.context.get('post_id'), self.post_1.id)

    def test_post_another_group(self):
        """Пост не попал в другую группу"""
        response = self.authorized_author.get(
            reverse('posts:group_list', kwargs={'slug': 'test-slug'}))
        first_object = response.context['page_obj'][0]
        self.assertNotEqual(first_object.text, self.post_2.text)

    def test_cache_index(self):
        """Проверка хранения и очищения кэша для index"""
        response = self.authorized_author.get(reverse('posts:index'))
        posts = response.content
        Post.objects.create(
            text='test_new_post',
            author=self.author,
        )
        response_old = self.authorized_author.get(reverse('posts:index'))
        old_posts = response_old.content
        self.assertEqual(old_posts, posts)
        cache.clear()
        response_new = self.authorized_author.get(reverse('posts:index'))
        new_posts = response_new.content
        self.assertNotEqual(old_posts, new_posts)


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author = User.objects.create_user(username='user_1')
        cls.group = Group.objects.create(
            title='test-group',
            slug='test-slug',
        )
        cls.post_1 = Post.objects.create(
            author=cls.author,
            group=cls.group,
            text='Тестовый пост 1',
        )
        lst = [
            Post(
                author=cls.author,
                group=cls.group,
                text=f'Тестовый пост {i}'
            )
            for i in range(1, 13)
        ]
        Post.objects.bulk_create(lst)

    def setUp(self):
        cache.clear()
        self.guest_client = Client()

    def test_page_cotains_correct_number_records(self):
        """Проверка правильного количества записей на страницах
           posts:index, posts:group_list, posts:profile
        """
        fields = {
            (reverse('posts:index'), 10),
            ((reverse('posts:index') + '?page=2'), 3),
            (reverse('posts:group_list', kwargs={'slug': 'test-slug'}),
             10),
            ((reverse('posts:group_list',
                      kwargs={'slug': 'test-slug'}) + '?page=2'), 3),
            (reverse('posts:profile', kwargs={'username': 'user_1'}),
             10),
            ((reverse('posts:profile',
                      kwargs={'username': 'user_1'}) + '?page=2'), 3),
        }
        for adress, records_number in fields:
            with self.subTest(adress=adress):
                response = self.client.get(adress)
                self.assertEqual(len(response.context['page_obj']),
                                 records_number)


class FollowTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.follower = User.objects.create(username='follower')
        cls.following = User.objects.create(username='following')
        cls.post = Post.objects.create(
            author=cls.following,
            text='Тестовый пост'
        )

    def setUp(self):
        self.client_follower = Client()
        self.client_following = Client()
        self.client_follower.force_login(self.follower)
        self.client_following.force_login(self.following)

    def test_follow(self):
        """Проверка на создание подписки"""
        self.client_follower.get(reverse('posts:profile_follow',
                                         kwargs={'username':
                                                 self.following.
                                                 username}))
        self.assertEqual(Follow.objects.all().count(), 1)

    def test_unfollow(self):
        """Проверка на удаление подписки"""
        self.client_follower.get(reverse('posts:profile_follow',
                                         kwargs={'username':
                                                 self.following.
                                                 username}))
        self.client_follower.get(reverse('posts:profile_unfollow',
                                         kwargs={'username':
                                                 self.following.
                                                 username}))
        self.assertEqual(Follow.objects.all().count(), 0)

    def new_post_in_follow(self):
        """Проверка наличия записи в списке подписок.
           И отсутствие записи, если подписки нет.
        """
        Follow.objects.create(
            user=self.follower,
            author=self.following
        )
        response = self.client_follower.get('/follow/')
        post_text = response.context['page_obj'][0].text
        self.assertEqual(post_text, 'Тестовый пост')
        response = self.client_following.get('/follow/')
        self.assertNotContains(response,
                               'Тестовый пост')
