import re
from django.shortcuts import render
from django.db.models import Q
from django.contrib import messages
from django.core.paginator import Paginator
from .forms import FilterForm
from modelCore.models import NewsArticle, Keyword, Industry
from .management.commands.fetch_news import NewsAPIClient, save_articles
from datetime import datetime, timedelta
from django.http import JsonResponse

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

def create_or_get_industry(name):
    """
    創建或獲取產業類別
    """
    if not name:
        return None
    
    # 清理產業名稱
    name = clean_text(name)
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
    # 如果是字符串，先分割成列表
    if isinstance(keyword_str, str):
        # 清理並分割關鍵字
        keyword_str = clean_text(keyword_str)
        keyword_list = [clean_text(k) for k in keyword_str.split(',') if clean_text(k)]
    else:
        # 如果已經是列表，清理每個元素
        keyword_list = [clean_text(k) for k in keyword_str if clean_text(k)]
    
    # 創建或獲取每個關鍵字
    for kw in keyword_list:
        if kw:  # 確保關鍵字不為空
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
        # 清理產業名稱
        industry_name = clean_text(industry_name)
        
        keyword_list = form.cleaned_data.get('keywords', [])
        # 清理關鍵字列表
        keyword_list = [clean_text(k) for k in keyword_list if clean_text(k)]
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
                    keyword = Keyword.objects.create(keyword=industry_name, industry=industry)
                    messages.success(request, f"已新增產業類別：{industry_name}")

            # 處理關鍵字
            for kw in keyword_list:
                keywords_to_fetch.add(kw)
                # 如果關鍵字不存在，創建它
                keyword_obj = Keyword.objects.filter(keyword=kw).first()
                if not keyword_obj:
                    keyword_obj = Keyword.objects.create(
                        keyword=kw,
                        industry=industry if industry_name else None
                    )
                    messages.success(request, f"已新增關鍵字：{kw}")

            if not keywords_to_fetch:
                messages.warning(request, "請選擇至少一個產業或關鍵字來獲取新聞")
            else:
                total_fetched = 0  # 總共嘗試獲取的文章數
                total_new_articles = 0  # 實際新增的文章數
                
                for keyword in keywords_to_fetch:
                    data, error = client.fetch_news(keyword, limit=5)
                    if error:
                        messages.error(request, error)
                        continue
                    
                    if data and 'articles' in data:
                        total_fetched += len(data['articles'])
                        keyword_obj = Keyword.objects.filter(keyword=keyword).first()
                        saved_count = save_articles(data.get('articles', []), keyword_obj)
                        total_new_articles += saved_count
                
                if total_fetched == 0:
                    messages.info(request, "沒有找到相關的新聞文章")
                elif total_new_articles > 0:
                    messages.success(request, f"成功獲取 {total_new_articles} 篇最新新聞！")
                    # 重新查詢文章列表，確保包含新獲取的文章
                    articles = NewsArticle.objects.all().order_by('-published_at')
                else:
                    messages.info(request, "找到的文章都已經存在，沒有新增新聞")
        
        # 篩選文章
        q = Q()
        
        # 處理產業篩選
        if industry_name:
            # 先查找產業關聯的文章
            industry_q = Q(industries__name=industry_name)
            # 再查找標題或描述中包含產業名稱的文章
            text_q = Q(title__icontains=industry_name) | Q(description__icontains=industry_name)
            # 查找該產業下所有關鍵字關聯的文章
            industry_keywords = Keyword.objects.filter(industry__name=industry_name)
            if industry_keywords.exists():
                keywords_q = Q(keywords__in=industry_keywords)
                q |= industry_q | text_q | keywords_q
            else:
                q |= industry_q | text_q
        
        # 處理關鍵字篩選
        if keyword_list:
            keyword_q = Q()
            for keyword in keyword_list:
                # 先查找關鍵字關聯的文章
                keyword_q |= Q(keywords__keyword=keyword)
                # 再查找標題或描述中包含關鍵字的文章
                keyword_q |= Q(title__icontains=keyword) | Q(description__icontains=keyword)
                
                # 檢查現有文章是否包含此關鍵字，如果包含則建立關聯
                keyword_obj = Keyword.objects.filter(keyword=keyword).first()
                if keyword_obj:
                    matching_articles = NewsArticle.objects.filter(
                        Q(title__icontains=keyword) | Q(description__icontains=keyword)
                    ).exclude(keywords=keyword_obj)
                    
                    for article in matching_articles:
                        article.keywords.add(keyword_obj)
            
            q |= keyword_q
        
        if q:
            articles = articles.filter(q).distinct()  # 使用 distinct() 去除重複
            
        # 如果篩選後沒有文章，且剛才成功獲取了新聞，重新進行關鍵字關聯
        if not articles.exists() and total_new_articles > 0:
            # 重新處理關鍵字關聯
            for keyword in keyword_list:
                keyword_obj = Keyword.objects.filter(keyword=keyword).first()
                if keyword_obj:
                    matching_articles = NewsArticle.objects.filter(
                        Q(title__icontains=keyword) | Q(description__icontains=keyword)
                    ).exclude(keywords=keyword_obj)
                    
                    for article in matching_articles:
                        article.keywords.add(keyword_obj)
            
            # 重新進行篩選
            if q:
                articles = NewsArticle.objects.filter(q).distinct()
    
    # 分頁處理
    page_number = request.GET.get('page', 1)
    paginator = Paginator(articles, 10)  # 移除這裡的 distinct() 因為已經在上面處理過了
    page_obj = paginator.get_page(page_number)
    
    # 對當前頁的文章進行預處理
    for article in page_obj:
        article.description = clean_text(article.description)
    
    context = {
        'form': form,
        'page_obj': page_obj,
        'total_count': articles.count(),
        'current_filters': request.GET.dict(),
    }
    return render(request, 'filter_news.html', context)

def get_industries(request):
    """獲取產業建議列表"""
    query = request.GET.get('q', '')
    industries = Industry.objects.filter(name__icontains=query)[:10]
    return JsonResponse(list(industries.values('name')), safe=False)

def get_keywords(request):
    """獲取關鍵字建議列表"""
    query = request.GET.get('q', '')
    industry = request.GET.get('industry', '')
    
    keywords = Keyword.objects.all()
    
    if industry:
        keywords = keywords.filter(industry__name=industry)
    
    if query:
        keywords = keywords.filter(keyword__icontains=query)
    
    return JsonResponse(list(keywords.values('keyword'))[:10], safe=False)
