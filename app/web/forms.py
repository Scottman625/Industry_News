from django import forms
from modelCore.models import Industry, Keyword

class FilterForm(forms.Form):
    TIME_RANGES = [
        ('all', '所有時間'),
        ('today', '今天'),
        ('week', '最近一週'),
        ('month', '最近一個月'),
    ]

    industry = forms.CharField(
        required=False,
        label='產業類別',
        widget=forms.Select(attrs={
            'class': 'form-select select2-with-tag',
            'data-placeholder': '選擇或輸入產業類別...',
            'data-allow-input': 'true'
        })
    )
    
    keywords = forms.CharField(
        required=False,
        label='關鍵字',
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select select2-with-tag',
            'data-placeholder': '選擇或輸入關鍵字...',
            'multiple': 'multiple',
            'data-allow-input': 'true'
        })
    )
    
    time_range = forms.ChoiceField(
        choices=TIME_RANGES,
        required=False,
        initial='all',
        label='時間範圍',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    fetch_new = forms.BooleanField(
        required=False,
        initial=False,
        label='立即更新',
        help_text='勾選此項可立即從網路獲取最新新聞',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 設置初始選項
        self.fields['industry'].widget.choices = [('', '選擇或輸入產業類別...')] + [
            (i.name, i.name) for i in Industry.objects.all()
        ]
        self.fields['keywords'].widget.choices = [('', '選擇或輸入關鍵字...')] + [
            (k.keyword, k.keyword) for k in Keyword.objects.all()
        ]
    
    def clean_industry(self):
        """處理產業輸入"""
        industry = self.cleaned_data.get('industry', '')
        if industry:
            # 如果輸入的產業不存在，則創建新的產業
            Industry.objects.get_or_create(name=industry)
        return industry

    def clean_keywords(self):
        """處理關鍵字輸入"""
        keywords = self.cleaned_data.get('keywords', '')
        if isinstance(keywords, str):
            # 如果是字符串，按逗號分割並清理空白
            keywords = [k.strip() for k in keywords.split(',') if k.strip()]
        elif isinstance(keywords, list):
            keywords = [k.strip() for k in keywords if k.strip()]
        
        # 為每個關鍵字創建記錄（如果不存在）
        for keyword in keywords:
            Keyword.objects.get_or_create(keyword=keyword)
        
        return keywords
    
    def clean(self):
        cleaned_data = super().clean()
        industry = cleaned_data.get('industry')
        keywords = cleaned_data.get('keywords', [])  # 已經被 clean_keywords 處理成列表
        fetch_new = cleaned_data.get('fetch_new')
        
        # 如果要獲取新聞，必須至少選擇一個產業或關鍵字
        if fetch_new and not (industry or keywords):
            raise forms.ValidationError("獲取新聞時必須選擇或輸入至少一個產業或關鍵字")
        
        return cleaned_data
