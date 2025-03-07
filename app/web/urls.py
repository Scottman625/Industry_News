from django.urls import path
from . import views

urlpatterns = [
    path('', views.filter_news, name='filter_news'),
    path('api/industries/', views.get_industries, name='get_industries'),
    path('api/keywords/', views.get_keywords, name='get_keywords'),
]