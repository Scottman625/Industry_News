from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.utils import timezone
from django.db.models import Q
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
    keyword = models.CharField(
        "關鍵字", 
        max_length=50,
        unique=True,  # 確保關鍵字全局唯一
    )
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
        # 清理關鍵字
        self.keyword = clean_text(self.keyword)
        
        # 如果清理後的關鍵字為空或太短，則不保存
        if not self.keyword or len(self.keyword) < 2:
            return
            
        # 檢查是否已存在相同的關鍵字（不區分大小寫）
        existing = Keyword.objects.filter(keyword__iexact=self.keyword).first()
        if existing and existing.id != self.id:
            # 如果已存在相同的關鍵字，則更新產業關聯（如果需要）
            if self.industry and not existing.industry:
                existing.industry = self.industry
                existing.save()
            return existing
            
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "關鍵字"
        verbose_name_plural = "關鍵字"
        indexes = [
            models.Index(fields=['keyword']),  # 添加索引以提升查詢效能
        ]

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
        # 清理文章內容
        clean_title = clean_text(self.title)
        clean_description = clean_text(self.description) if self.description else ""
        
        # 將標題和描述合併成一個文本進行搜索
        article_text = f" {clean_title} {clean_description} ".lower()
        
        # 獲取所有產業
        all_industries = Industry.objects.all()
        relevant_industries = set()
        
        # 第一步：找出所有相關的產業
        for industry in all_industries:
            clean_industry_name = clean_text(industry.name)
            print(f'clean_industry_name: {clean_industry_name}')
            if not clean_industry_name or len(clean_industry_name) < 2:
                continue
            
            # 檢查產業名稱是否出現在文章中（使用完整詞匹配）
            if f" {clean_industry_name.lower()} " in article_text:
                relevant_industries.add(industry)
        
        # 清除所有不相關的產業關聯
        for industry in self.industries.all():
            if industry not in relevant_industries:
                self.industries.remove(industry)
        
        # 添加新發現的相關產業
        for industry in relevant_industries:
            if not self.industries.filter(id=industry.id).exists():
                self.industries.add(industry)
        
        # 第二步：處理關鍵字
        # 先移除所有現有的關鍵字關聯
        self.keywords.clear()
        
        # 只檢查相關產業的關鍵字
        for industry in relevant_industries:
            industry_keywords = Keyword.objects.filter(industry=industry)
            
            for keyword in industry_keywords:
                clean_keyword = clean_text(keyword.keyword)
                print(f'clean_keyword: {clean_keyword}')
                if not clean_keyword or len(clean_keyword) < 2:
                    continue
                
                # 使用完整詞匹配來檢查關鍵字
                if f" {clean_keyword.lower()} " in article_text:
                    self.keywords.add(keyword)

    def save(self, *args, **kwargs):
        # 清理文章內容
        self.title = clean_text(self.title)
        if self.description:
            self.description = clean_text(self.description)
        
        # 檢查是否為新建立的文章
        is_new = self._state.adding
        
        # 先保存文章本身
        super().save(*args, **kwargs)
        
        # 執行關鍵字檢測（每次保存都執行，確保關聯始終正確）
        self.detect_and_link_industries_keywords()
