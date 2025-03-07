from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.utils import timezone
# Create your models here.
# news_app/models.py

def clean_text(text):
    """
    清理文字，移除不必要的符號和空白
    """
    if not text:
        return ""
    
    # 如果是列表，取第一個元素
    if isinstance(text, list):
        text = text[0] if text else ""
        
    # 處理字符串
    if isinstance(text, str):
        # 如果文字看起來像列表字符串，嘗試解析它
        if text.startswith('[') and text.endswith(']'):
            try:
                import ast
                # 安全地解析字符串為Python對象
                parsed = ast.literal_eval(text)
                if isinstance(parsed, list) and parsed:
                    text = parsed[0]
            except:
                pass
        
        # 移除可能的列表符號和引號
        text = text.strip('[]\'\"')
        # 移除額外的空白
        text = text.strip()
        
    return text

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

    def save(self, *args, **kwargs):
        self.name = clean_text(self.name)
        super().save(*args, **kwargs)

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

    def save(self, *args, **kwargs):
        self.keyword = clean_text(self.keyword)
        super().save(*args, **kwargs)

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
        # 先檢查文章是否已有關聯的產業
        existing_industries = self.industries.all()
        
        for industry in existing_industries:
            # 只檢查該產業下的關鍵字
            industry_keywords = Keyword.objects.filter(industry=industry)
            
            # 檢查標題和描述中的關鍵字（使用完整詞匹配）
            for keyword in industry_keywords:
                # 避免重複添加已存在的關鍵字
                if not self.keywords.filter(id=keyword.id).exists():
                    # 使用完整詞匹配來檢查
                    clean_keyword = clean_text(keyword.keyword)
                    clean_title = clean_text(self.title)
                    clean_description = clean_text(self.description)
                    
                    if ((clean_title and f" {clean_keyword} " in f" {clean_title} ") or 
                        (clean_description and f" {clean_keyword} " in f" {clean_description} ")):
                        self.keywords.add(keyword)

    def save(self, *args, **kwargs):
        # 清理文章內容
        self.title = clean_text(self.title)
        if self.description:
            self.description = clean_text(self.description)
        
        # 先保存文章本身
        super().save(*args, **kwargs)
        # 然後檢測並關聯產業和關鍵字
        self.detect_and_link_industries_keywords()
