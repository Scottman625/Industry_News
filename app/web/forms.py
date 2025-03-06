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
            'data-placeholder': '選擇或輸入產業類別...'
        })
    )
    
    keywords = forms.CharField(
        required=False,
        label='關鍵字',
        widget=forms.Select(attrs={
            'class': 'form-select select2-with-tag',
            'data-placeholder': '選擇或輸入關鍵字...',
            'multiple': 'multiple'
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
    
    def clean(self):
        cleaned_data = super().clean()
        industry = cleaned_data.get('industry')
        keywords = cleaned_data.get('keywords', '').split(',')  # 將多選的值分割成列表
        keywords = [k.strip() for k in keywords if k.strip()]  # 清理空白
        fetch_new = cleaned_data.get('fetch_new')
        
        # 如果要獲取新聞，必須至少選擇一個產業或關鍵字
        if fetch_new and not (industry or keywords):
            raise forms.ValidationError("獲取新聞時必須選擇或輸入至少一個產業或關鍵字")
        
        # 更新清理後的關鍵字
        cleaned_data['keywords'] = keywords
        return cleaned_data
