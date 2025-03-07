from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.utils import timezone
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
    name = models.CharField("產業名稱", max_length=50, unique=True)
    created_at = models.DateTimeField("建立時間", default=timezone.now)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "產業"
        verbose_name_plural = "產業"

class Keyword(models.Model):
    keyword = models.CharField("關鍵字", max_length=50)
    industry = models.ForeignKey(
        Industry, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='keywords',
        verbose_name="相關產業"
    )
    created_at = models.DateTimeField("建立時間", default=timezone.now)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    def __str__(self):
        return self.keyword

    class Meta:
        verbose_name = "關鍵字"
        verbose_name_plural = "關鍵字"

class NewsArticle(models.Model):
    title = models.CharField("標題", max_length=200)
    description = models.TextField("描述", null=True, blank=True)
    url = models.URLField("連結", unique=True)
    source = models.CharField("來源", max_length=100)
    published_at = models.DateTimeField("發布時間", null=True)
    created_at = models.DateTimeField("建立時間", default=timezone.now)
    
    # 新增產業和關鍵字關聯
    industries = models.ManyToManyField(
        Industry, 
        blank=True,
        related_name='news_articles',
        verbose_name="相關產業"
    )
    keywords = models.ManyToManyField(
        Keyword, 
        blank=True,
        related_name='news_articles',
        verbose_name="相關關鍵字"
    )

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "新聞文章"
        verbose_name_plural = "新聞文章"
        ordering = ['-published_at']

    def detect_and_link_industries_keywords(self):
        """
        檢測文章內容中的產業和關鍵字，並建立關聯
        """
        # 獲取所有關鍵字
        all_keywords = Keyword.objects.all()
        
        # 檢查標題和描述中的關鍵字
        for keyword in all_keywords:
            if (keyword.keyword in self.title or 
                (self.description and keyword.keyword in self.description)):
                # 添加關鍵字關聯
                self.keywords.add(keyword)
                # 如果關鍵字有關聯的產業，也添加產業關聯
                if keyword.industry:
                    self.industries.add(keyword.industry)

    def save(self, *args, **kwargs):
        # 先保存文章本身
        super().save(*args, **kwargs)
        # 然後檢測並關聯產業和關鍵字
        self.detect_and_link_industries_keywords()
