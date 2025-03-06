from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
# Create your models here.
# news_app/models.py

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """Creates and saves a new user"""
        if not email:
            raise ValueError("Users must have an email address")
        # user = self.model(email=self.normalize_email(email), **extra_fields)
        user = self.model(
            email=self.normalize_email(email),
            name=extra_fields.get("name"),
            fb_id=extra_fields.get("fb_id"),
            google_id=extra_fields.get("google_id"),
            apple_id=extra_fields.get("apple_id"),
            line_id=extra_fields.get("line_id"),
        )
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password, **extra_fields):
        """Creates and saves a new super user"""
        user = self.create_user(email, password, **extra_fields)

        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)

        return user


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model that suppors using email instead of username"""

    email = models.EmailField(max_length=255, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    # account_balance = models.IntegerField(default=0)


    objects = UserManager()

    fb_id = models.CharField(max_length=255, default="", blank=True, null=True)
    google_id = models.CharField(max_length=255, default="", blank=True, null=True)
    apple_id = models.CharField(max_length=255, default="", blank=True, null=True)
    line_id = models.CharField(max_length=255, default="", blank=True, null=True)
    OPEN_API_Key = models.CharField(max_length=255, default="", blank=True, null=True)
    Secret_Key = models.CharField(max_length=255, default="", blank=True, null=True)

    USERNAME_FIELD = "email"

class Industry(models.Model):
    name = models.CharField(max_length=100, verbose_name="產業名稱")
    description = models.TextField(blank=True, null=True, verbose_name="產業描述")

    def __str__(self):
        return self.name

class Keyword(models.Model):
    keyword = models.CharField(max_length=100, verbose_name="關鍵字")
    industry = models.ForeignKey(Industry, on_delete=models.CASCADE, related_name='keywords', verbose_name="所屬產業")

    def __str__(self):
        return self.keyword

class NewsArticle(models.Model):
    title = models.CharField(max_length=255, verbose_name="標題")
    description = models.TextField(blank=True, null=True, verbose_name="摘要")
    url = models.URLField(unique=True, verbose_name="文章連結")
    source = models.CharField(max_length=255, verbose_name="來源")
    published_at = models.DateTimeField(verbose_name="發布時間")

    def __str__(self):
        return self.title
