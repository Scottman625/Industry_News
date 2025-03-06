from django.urls import path
from .views import filter_news

urlpatterns = [
    path('filter/', filter_news, name='filter_news'),
]