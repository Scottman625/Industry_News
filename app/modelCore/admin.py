from django.contrib import admin
from .models import User
from .models import Industry, Keyword, NewsArticle
# Register your models here.

admin.site.register(User)
admin.site.register(Industry)
admin.site.register(Keyword)
admin.site.register(NewsArticle)



