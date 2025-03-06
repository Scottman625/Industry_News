import re
from django.shortcuts import render
from django.db.models import Q
from django.contrib import messages
from django.core.paginator import Paginator
from .forms import FilterForm
from modelCore.models import NewsArticle, Keyword, Industry
from .management.commands.fetch_news import NewsAPIClient, save_articles
from datetime import datetime, timedelta

def preprocess_text(text):
    """
    預處理文章內容：
    - 移除 HTML 標籤
    - 移除多餘的空白
    """
    if not text:
        return ""
    # 移除 HTML 標籤
    text = re.sub(r'<[^>]+>', '', text)
    # 移除多餘空白
    text = ' '.join(text.split())
    return text

def create_or_get_industry(name):
    """
    創建或獲取產業類別
    """
    name = name.strip()
    if not name:
        return None
    industry, created = Industry.objects.get_or_create(name=name)
    return industry

def create_or_get_keywords(keyword_str, industry=None):
    """
    創建或獲取關鍵字列表
    """
    if not keyword_str:
        return []
    
    keywords = []
    for kw in [k.strip() for k in keyword_str.split(',') if k.strip()]:
        keyword, created = Keyword.objects.get_or_create(
            keyword=kw,
            defaults={'industry': industry}
        )
        keywords.append(keyword)
    return keywords

def filter_news(request):
    form = FilterForm(request.GET or None)
    articles = NewsArticle.objects.all().order_by('-published_at')
    
    if form.is_valid():
        industry_name = form.cleaned_data.get('industry')
        keyword_list = form.cleaned_data.get('keywords', [])
        fetch_new = form.cleaned_data.get('fetch_new', False)
        time_range = form.cleaned_data.get('time_range', 'all')
        
        # 時間範圍篩選
        if time_range != 'all':
            today = datetime.now()
            start_date = None
            
            if time_range == 'today':
                start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            elif time_range == 'week':
                start_date = today - timedelta(days=7)
            elif time_range == 'month':
                start_date = today - timedelta(days=30)
            
            if start_date:
                articles = articles.filter(published_at__gte=start_date)
        
        if fetch_new:
            # 獲取最新新聞
            client = NewsAPIClient()
            total_new_articles = 0
            keywords_to_fetch = set()

            # 處理產業關鍵字
            if industry_name:
                # 嘗試獲取現有產業
                industry = Industry.objects.filter(name=industry_name).first()
                if industry:
                    # 如果產業存在，獲取其關鍵字
                    industry_keywords = Keyword.objects.filter(industry=industry)
                    keywords_to_fetch.update(k.keyword for k in industry_keywords)
                else:
                    # 如果產業不存在，直接使用產業名稱作為關鍵字
                    keywords_to_fetch.add(industry_name)
                    # 創建新產業和關鍵字
                    industry = Industry.objects.create(name=industry_name)
                    Keyword.objects.create(keyword=industry_name, industry=industry)
                    messages.success(request, f"已新增產業類別：{industry_name}")

            # 處理關鍵字
            for kw in keyword_list:
                keywords_to_fetch.add(kw)
                # 如果關鍵字不存在，創建它
                if not Keyword.objects.filter(keyword=kw).exists():
                    Keyword.objects.create(
                        keyword=kw,
                        industry=industry if industry_name else None
                    )
                    messages.success(request, f"已新增關鍵字：{kw}")

            if not keywords_to_fetch:
                messages.warning(request, "請選擇至少一個產業或關鍵字來獲取新聞")
            else:
                for keyword in keywords_to_fetch:
                    data, error = client.fetch_news(keyword, limit=5)
                    if error:
                        messages.error(request, error)
                        continue
                    
                    saved_count = save_articles(data.get('articles', []))
                    total_new_articles += saved_count
                
                if total_new_articles > 0:
                    messages.success(request, f"成功獲取 {total_new_articles} 篇最新新聞！")
                else:
                    messages.info(request, "沒有找到新的文章")
        
        # 篩選文章
        q = Q()
        
        # 處理產業篩選
        if industry_name:
            # 先查找產業關鍵字
            industry_keywords = Keyword.objects.filter(
                industry__name=industry_name
            ).values_list('keyword', flat=True)
            
            if industry_keywords:
                # 如果有產業關鍵字，用它們來搜尋
                for kw in industry_keywords:
                    q |= Q(title__icontains=kw) | Q(description__icontains=kw)
            else:
                # 如果沒有產業關鍵字，直接用產業名稱搜尋
                q |= Q(title__icontains=industry_name) | Q(description__icontains=industry_name)
        
        # 處理關鍵字篩選
        for keyword in keyword_list:
            q |= Q(title__icontains=keyword) | Q(description__icontains=keyword)
        
        if q:
            articles = articles.filter(q)
    
    # 分頁處理
    page_number = request.GET.get('page', 1)
    paginator = Paginator(articles, 10)  # 每頁顯示10篇文章
    page_obj = paginator.get_page(page_number)
    
    # 對當前頁的文章進行預處理
    for article in page_obj:
        article.description = preprocess_text(article.description)
    
    context = {
        'form': form,
        'page_obj': page_obj,
        'total_count': articles.count(),
        'current_filters': request.GET.dict(),
    }
    return render(request, 'filter_news.html', context)
