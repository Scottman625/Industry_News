# news_app/management/commands/fetch_news.py

import requests
from django.core.management.base import BaseCommand
from modelCore.models import Keyword, NewsArticle, Industry
from datetime import datetime
import os

class NewsAPIClient:
    def __init__(self):
        self.api_key = os.getenv('NEWS_API_KEY')
        self.api_url = 'https://newsapi.org/v2/everything'

    def fetch_news(self, keywords, industry_keywords=None, limit=5):
        """
        獲取指定關鍵字的新聞
        keywords: 可以是單個關鍵字字符串或關鍵字列表
        industry_keywords: 產業相關的關鍵字列表
        """
        # 如果是單個關鍵字，轉換為列表
        if isinstance(keywords, str):
            keywords = [keywords]
        if industry_keywords:
            # 如果有產業關鍵字，將每個產業關鍵字與一般關鍵字組合
            combined_queries = []
            for ind_kw in industry_keywords:
                for kw in keywords:
                    combined_queries.append(f'("{ind_kw}" AND "{kw}")')
            query = ' OR '.join(combined_queries)
        else:
            query = ' OR '.join(f'"{k}"' for k in keywords)
        
        params = {
            'q': query,
            'apiKey': self.api_key,
            'language': 'zh',
            'sortBy': 'publishedAt',
            'pageSize': limit
        }
        
        response = requests.get(self.api_url, params=params)
        if response.status_code != 200:
            return None, f"抓取關鍵字 {query} 失敗，狀態碼：{response.status_code}"
            
        return response.json(), None

def save_articles(articles, keyword_obj=None, stdout=None):
    """
    儲存新聞文章到資料庫，並建立關鍵字和產業關聯
    """
    saved_count = 0
    for article in articles:
        published_at = article.get('publishedAt')
        try:
            published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except Exception:
            published_at = None

        # 清理文章內容
        title = article.get('title', '')
        description = article.get('description', '')
        source = article.get('source', {}).get('name', '')

        try:
            news, created = NewsArticle.objects.get_or_create(
                url=article['url'],
                defaults={
                    'title': title,
                    'description': description,
                    'source': source,
                    'published_at': published_at,
                }
            )

            if created:
                # 如果有關鍵字物件，添加關聯
                if keyword_obj:
                    news.keywords.add(keyword_obj)
                    # 如果關鍵字有關聯的產業，也添加產業關聯
                    if keyword_obj.industry:
                        news.industries.add(keyword_obj.industry)
                
                saved_count += 1
                if stdout:
                    stdout.write(f"儲存文章：{news.title}")
                    
        except Exception as e:
            if stdout:
                stdout.write(f"儲存文章時發生錯誤：{str(e)}")
            continue
    
    return saved_count

class Command(BaseCommand):
    help = "根據關鍵字字庫抓取新聞文章"

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='每個關鍵字要抓取的最新文章數量（預設：5）'
        )
        parser.add_argument(
            '--keyword',
            type=str,
            help='指定要查詢的關鍵字'
        )
        parser.add_argument(
            '--industry',
            type=str,
            help='指定要查詢的產業名稱'
        )

    def handle(self, *args, **options):
        client = NewsAPIClient()
        article_limit = options['limit']
        keyword_query = options['keyword']
        industry_name = options['industry']

        # 手動查詢模式
        if keyword_query or industry_name:
            keywords_to_fetch = []
            
            # 如果指定了關鍵字
            if keyword_query:
                keywords_to_fetch = Keyword.objects.filter(keyword__icontains=keyword_query)
                
            # 如果指定了產業
            if industry_name:
                try:
                    industry = Industry.objects.get(name=industry_name)
                    industry_keywords = Keyword.objects.filter(industry=industry)
                    keywords_to_fetch = keywords_to_fetch.union(industry_keywords)
                except Industry.DoesNotExist:
                    self.stderr.write(f"找不到產業：{industry_name}")
                    return

            if not keywords_to_fetch:
                self.stderr.write("找不到符合的關鍵字")
                return

        # 排程任務模式
        else:
            keywords_to_fetch = Keyword.objects.all()
            if not keywords_to_fetch.exists():
                self.stdout.write("尚未建立任何關鍵字，請先在後台新增。")
                return

        total_articles = 0
        for keyword in keywords_to_fetch:
            self.stdout.write(f"開始抓取關鍵字「{keyword.keyword}」的最新 {article_limit} 篇文章")
            
            data, error = client.fetch_news(keyword.keyword, keyword.industry.keywords.all() if keyword.industry else None, article_limit)
            if error:
                self.stderr.write(error)
                continue
                
            saved_count = save_articles(data.get('articles', []), keyword, self.stdout)
            total_articles += saved_count

        self.stdout.write(f"完成！共儲存 {total_articles} 篇新文章。")
