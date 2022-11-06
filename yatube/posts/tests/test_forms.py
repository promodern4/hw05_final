import shutil
import tempfile

from http import HTTPStatus
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from posts.models import Post, Group, Comment

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)
User = get_user_model()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostCreateFormTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author = User.objects.create_user(username='author')
        cls.user = User.objects.create_user(username='user')
        cls.group = Group.objects.create(
            title='test-group',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post_1 = Post.objects.create(
            author=cls.author,
            group=cls.group,
            text='Тестовый пост',
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.author)

    def test_create_post_not_authorized(self):
        """Проверка создания поста неавторизованным пользователем"""
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Новый пост',
            'group': self.group.id,
            'author': self.user,
        }
        self.guest.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        self.assertEqual(Post.objects.count(), posts_count)

    def test_create_post_authorized(self):
        """Проверка на создание поста"""
        posts_count = Post.objects.count()
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

        form_data = {
            'text': 'Новый пост',
            'group': self.group.id,
            'author': self.user,
            'image': uploaded
        }
        self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        self.assertEqual(Post.objects.count(), posts_count + 1)
        post = Post.objects.get(
            group=self.group.id,
            text='Новый пост',
        )
        self.assertEqual(post.text, 'Новый пост')
        self.assertEqual(post.group.id, self.group.id)
        self.assertEqual(post.author, self.author)
        self.assertEqual(post.image, 'posts/small.gif')

    def test_post_edit_authorized(self):
        """Проверка редактирования поста"""
        editing_post = self.post_1
        form_data = {
            'text': 'Измененный пост',
            'group': self.group.id,
            'author': self.user
        }
        response = self.authorized_client.post(
            reverse('posts:post_edit',
                    kwargs={
                        'post_id': editing_post.id,
                    }),
            data=form_data,
            follow=True,
        )
        edited_post = Post.objects.get(
            group=self.group.id,
            text='Измененный пост'
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(edited_post.text, 'Измененный пост')
        self.assertEqual(edited_post.group.id, self.group.id)
        self.assertEqual(edited_post.author, self.author)

    def test_create_comment_not_authorized(self):
        """Проверка создания комментария неавторизованным клиентом"""
        commenting_post = self.post_1
        comments_count = Comment.objects.filter(post=self.post_1.id).count()
        form_data = {
            'text': 'Новый комментарий',
        }
        self.guest.post(
            reverse('posts:add_comment',
                    kwargs={
                        'post_id': commenting_post.id,
                    }
                    ),
            data=form_data,
            follow=True
        )
        self.assertEqual(Comment.objects.filter(post=self.post_1.id).count(),
                         comments_count)

    def test_create_comment_authorized(self):
        """Проверка создания комментария"""
        commenting_post = self.post_1
        comments_count = Comment.objects.filter(post=self.post_1.id).count()
        form_data = {
            'text': 'Новый комментарий',
        }
        self.authorized_client.post(
            reverse('posts:add_comment',
                    kwargs={
                        'post_id': commenting_post.id,
                    }
                    ),
            data=form_data,
            follow=True
        )
        self.assertEqual(Comment.objects.filter(post=self.post_1.id).count(),
                         comments_count + 1)
        comment = Comment.objects.get(
            text='Новый комментарий'
        )
        self.assertEqual(comment.text, 'Новый комментарий')
        self.assertEqual(comment.author, self.author)
        self.assertEqual(comment.post.id, self.post_1.id)
