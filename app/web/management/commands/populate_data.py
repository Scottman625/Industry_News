# news_app/management/commands/populate_data.py

from django.core.management.base import BaseCommand
from modelCore.models import Industry, Keyword

class Command(BaseCommand):
    help = "將產業與關鍵字樣本資料加入資料庫"

    def handle(self, *args, **options):
        # 定義產業與關鍵字的清單
        data = {
            '科技': ['AI', '大數據', '雲端', '5G', '物聯網'],
            '金融': ['投資', '金融科技', '銀行', '匯率', '股市', '保險'],
            '生技': ['生物科技', '基因', '醫療', '新藥研發', '健康'],
            '電商': ['電子商務', '網購', '跨境電商', '物流', '支付'],
            '製造': ['工業4.0', '智慧製造', '自動化', '機械'],
            '新能源': ['太陽能', '風能', '電動車', '電池技術', '清潔能源'],
        }

        # 依據資料建立 Industry 與 Keyword 資料
        for industry_name, keywords in data.items():
            industry, created = Industry.objects.get_or_create(name=industry_name)
            if created:
                self.stdout.write(f"建立產業：{industry_name}")
            else:
                self.stdout.write(f"產業 {industry_name} 已存在")
            for kw in keywords:
                keyword, created = Keyword.objects.get_or_create(keyword=kw, industry=industry)
                if created:
                    self.stdout.write(f"   新增關鍵字：{kw}")
                else:
                    self.stdout.write(f"   關鍵字 {kw} 已存在")
        self.stdout.write("樣本資料載入完成！")
