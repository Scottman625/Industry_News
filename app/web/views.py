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
        
        # 移除或替換特殊字符
        text = re.sub(r'[-_]+', ' ', text)  # 將連字符和底線替換為空格
        text = re.sub(r'\s+', ' ', text)    # 將多個空格替換為單個空格
        text = text.strip()                  # 再次清理前後空白
        
        # 如果清理後的文字太短或只包含特殊字符或空白，返回空字符串
        if not text or len(text) < 2 or not any(c.isalnum() for c in text):
            return ""
        
    return text

def create_or_get_industry(name):
    """
    創建或獲取產業類別
    """
    if not name:
        return None
    
    # 清理產業名稱
    name = clean_text(name)
    if not name or len(name) < 1:
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
        if not keyword_str:  # 如果清理後為空，直接返回
            return []
        keyword_list = [clean_text(k) for k in keyword_str.split(',')]
    else:
        # 如果已經是列表，清理每個元素
        keyword_list = [clean_text(k) for k in keyword_str]
    
    # 過濾掉空白或無效的關鍵字
    keyword_list = [k for k in keyword_list if k and len(k) >= 2 and not k.isspace()]
    
    # 創建或獲取每個關鍵字
    for kw in keyword_list:
        kw = clean_text(kw)  # 再次清理確保乾淨
        if kw and len(kw) >= 2 and not kw.isspace():  # 確保關鍵字有效
            # 檢查是否已存在相同的關鍵字（不區分大小寫）
            existing_keyword = Keyword.objects.filter(keyword__iexact=kw).first()
            if existing_keyword:
                # 如果關鍵字已存在，直接使用現有的
                keywords.append(existing_keyword)
            else:
                # 如果關鍵字不存在，創建新的
                try:
                    keyword = Keyword.objects.create(
                        keyword=kw,
                        industry=industry
                    )
                    keywords.append(keyword)
                except Exception as e:
                    # 如果創建過程中出現錯誤，記錄錯誤但繼續處理
                    print(f"Error creating keyword '{kw}': {str(e)}")
                    continue
    return keywords

def filter_news(request):
    form = FilterForm(request.GET or None)
    articles = NewsArticle.objects.all().order_by('-published_at')
    total_new_articles = 0  # 初始化變數
    
    if form.is_valid():
        industry_name = form.cleaned_data.get('industry')
        # 清理產業名稱
        industry_name = clean_text(industry_name)
        
        keyword_list = form.cleaned_data.get('keywords', [])
        # 清理關鍵字列表，並移除無效的關鍵字
        keyword_list = [k for k in [clean_text(k) for k in keyword_list] if k and len(k) >= 2 and not k.isspace()]
        
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
            keywords_to_fetch = set()

            # 處理產業關鍵字
            if industry_name and len(industry_name) >= 2 and not industry_name.isspace():
                # 嘗試獲取現有產業
                industry = Industry.objects.filter(name=industry_name).first()
                if industry:
                    # 如果產業存在，獲取其關鍵字
                    industry_keywords = Keyword.objects.filter(industry=industry)
                    keywords_to_fetch.update(k.keyword for k in industry_keywords if k.keyword and len(k.keyword) >= 2 and not k.keyword.isspace())
                else:
                    # 如果產業不存在，直接使用產業名稱作為關鍵字
                    keywords_to_fetch.add(industry_name)
                    # 創建新產業和關鍵字
                    industry = Industry.objects.create(name=industry_name)
                    # 檢查是否已存在相同的關鍵字
                    existing_keyword = Keyword.objects.filter(keyword__iexact=industry_name).first()
                    if not existing_keyword and len(industry_name) >= 2 and not industry_name.isspace():
                        keyword = Keyword.objects.create(keyword=industry_name, industry=industry)
                        messages.success(request, f"已新增產業類別：{industry_name}")

            # 處理一般關鍵字
            for kw in keyword_list:
                kw = clean_text(kw)
                if kw and len(kw) >= 2 and not kw.isspace():
                    keywords_to_fetch.add(kw)
                    # 檢查是否已存在相同的關鍵字
                    keyword_obj = Keyword.objects.filter(keyword__iexact=kw).first()
                    if not keyword_obj:
                        try:
                            keyword_obj = Keyword.objects.create(
                                keyword=kw,
                                industry=industry if industry_name else None
                            )
                            messages.success(request, f"已新增關鍵字：{kw}")
                        except Exception as e:
                            print(f"Error creating keyword '{kw}': {str(e)}")
                            continue

            if not keywords_to_fetch:
                messages.warning(request, "請選擇至少一個產業或關鍵字來獲取新聞")
            else:
                # 分離產業關鍵字和一般關鍵字
                industry_keywords = None
                search_keywords = []
                
                if industry_name:
                    industry = Industry.objects.filter(name=industry_name).first()
                    if industry:
                        industry_keywords = [k.keyword for k in Keyword.objects.filter(industry=industry)]
                
                # 只使用用戶選擇的關鍵字進行搜尋
                search_keywords = keyword_list if keyword_list else [industry_name]
                
                # 一次性獲取所有關鍵字的新聞
                data, error = client.fetch_news(
                    search_keywords,
                    industry_keywords=industry_keywords,
                    limit=10
                )
                
                if error:
                    messages.error(request, error)
                else:
                    total_fetched = len(data.get('articles', [])) if data and 'articles' in data else 0
                    
                    if total_fetched > 0:
                        # 為每個關鍵字建立關聯
                        saved_articles = []  # 用於存儲新保存的文章
                        for keyword in keywords_to_fetch:
                            keyword_obj = Keyword.objects.filter(keyword=keyword).first()
                            if keyword_obj and data and 'articles' in data:
                                saved_count = save_articles(data.get('articles', []), keyword_obj)
                                total_new_articles += saved_count
                        
                        if total_new_articles > 0:
                            messages.success(request, f"成功獲取 {total_new_articles} 篇最新新聞！")
                            
                            # 根據當前的篩選條件重新查詢文章
                            q = Q()
                            
                            # 處理產業篩選
                            if industry_name:
                                industry_q = Q(industries__name=industry_name)
                                text_q = Q(title__icontains=industry_name) | Q(description__icontains=industry_name)
                                industry_keywords = Keyword.objects.filter(industry__name=industry_name)
                                if industry_keywords.exists():
                                    keywords_q = Q(keywords__in=industry_keywords)
                                    q = industry_q | text_q | keywords_q
                                else:
                                    q = industry_q | text_q
                            
                            # 處理關鍵字篩選
                            if keyword_list:
                                keyword_q = Q()
                                for keyword in keyword_list:
                                    keyword_q |= Q(keywords__keyword=keyword)
                                    keyword_q |= Q(title__icontains=keyword) | Q(description__icontains=keyword)
                                
                                if industry_name:
                                    q &= keyword_q
                                else:
                                    q = keyword_q
                            
                            # 使用篩選條件查詢文章
                            if q:
                                articles = NewsArticle.objects.filter(q).distinct().order_by('-published_at')
                            else:
                                articles = NewsArticle.objects.all().order_by('-published_at')
                        else:
                            messages.info(request, "找到的文章都已經存在，沒有新增新聞")
                    else:
                        messages.info(request, "沒有找到相關的新聞文章")
        
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
                q = industry_q | text_q | keywords_q
            else:
                q = industry_q | text_q
        
        # 處理關鍵字篩選
        if keyword_list:
            keyword_q = Q()
            for keyword in keyword_list:
                # 查找關鍵字關聯的文章
                keyword_q |= Q(keywords__keyword=keyword)
                # 查找標題或描述中包含關鍵字的文章
                keyword_q |= Q(title__icontains=keyword) | Q(description__icontains=keyword)
            
            # 如果同時有產業和關鍵字，使用 AND (&) 運算符
            if industry_name:
                q &= keyword_q
            else:
                q = keyword_q
        
        if q:
            articles = articles.filter(q).distinct()  # 使用 distinct() 去除重複
    
    # 分頁處理
    page_number = request.GET.get('page', 1)
    paginator = Paginator(articles, 10)
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
    
    # 清理查詢字符串
    query = clean_text(query)
    industry = clean_text(industry)
    
    # 排除預設提示文字和空選項
    excluded_keywords = ['選擇或輸入關鍵字...', '', None]
    
    # 使用 distinct 確保關鍵字不重複，同時排除空白或無效的關鍵字
    keywords = Keyword.objects.exclude(
        Q(keyword__in=excluded_keywords) |
        Q(keyword__isnull=True) |
        Q(keyword__exact='') |
        Q(keyword__regex=r'^\s*$')
    ).values('keyword').distinct()
    
    if industry:
        # 如果選擇了產業，優先顯示該產業的關鍵字，但也包含其他關鍵字
        industry_keywords = Keyword.objects.filter(
            industry__name=industry,
            keyword__icontains=query if query else ''
        ).exclude(
            Q(keyword__in=excluded_keywords) |
            Q(keyword__isnull=True) |
            Q(keyword__exact='') |
            Q(keyword__regex=r'^\s*$')
        ).values_list('keyword', flat=True)
        
        other_keywords = Keyword.objects.exclude(
            industry__name=industry
        ).filter(
            keyword__icontains=query if query else ''
        ).exclude(
            Q(keyword__in=excluded_keywords) |
            Q(keyword__isnull=True) |
            Q(keyword__exact='') |
            Q(keyword__regex=r'^\s*$')
        ).values_list('keyword', flat=True)
        
        # 合併結果，確保產業關鍵字優先顯示，並移除重複項
        all_keywords = list(industry_keywords) + list(set(other_keywords) - set(industry_keywords))
        # 過濾掉空白、無效或預設的關鍵字
        all_keywords = [k for k in all_keywords if k and k not in excluded_keywords and clean_text(k)]
        return JsonResponse([{'keyword': k} for k in all_keywords[:10]], safe=False)
    
    if query:
        keywords = keywords.filter(keyword__icontains=query)
    
    # 過濾掉空白、無效或預設的關鍵字
    keywords_list = [k['keyword'] for k in keywords.values('keyword') if k['keyword'] and k['keyword'] not in excluded_keywords and clean_text(k['keyword'])]
    return JsonResponse([{'keyword': k} for k in keywords_list[:10]], safe=False)
