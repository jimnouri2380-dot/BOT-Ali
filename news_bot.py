import requests
from bs4 import BeautifulSoup
import time
import os
import json
from deep_translator import GoogleTranslator

# ========== گرفتن توکن و چت آیدی از Secrets گیت‌هاب ==========
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ========== مشخصات سایت Ynet با سلکتورهای جدید ==========
SITE_CONFIG = {
    "name": "Ynet - اخبار سیاسی",
    "url": "https://www.ynet.co.il/home/0,7340,L-8,00.html",  # لینک جدیدی که دادید
    "article_selector": "div.article-item, div.accordeon, div[class*='article']",  # سلکتور کلی برای هر خبر
    "link_selector": "a[href*='/news/article/']",  # لینک خبر
    "title_selector": "#ArticleHeaderComponent > div.mainTitleWrapper > h1",  # سلکتور تیتر
    "lead_selector": "#ArticleHeaderComponent > div.subTitleWrapper",  # سلکتور لیدر
    "image_selector": "div.mainImage img, div.imageWrap img",  # سلکتور عکس
    "body_selector": "div.textWrap div.paragraphs p"  # سلکتور متن
}

# ========== مدیریت خبرهای تکراری ==========
SENT_FILE = "sent_news.json"

def load_sent_urls():
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_sent_urls(sent_set):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent_set), f, ensure_ascii=False)

sent_urls = load_sent_urls()

# ========== استخراج اخبار از Ynet ==========
def fetch_ynet_news():
    try:
        response = requests.get(SITE_CONFIG["url"], timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.select(SITE_CONFIG["article_selector"])
        news_list = []
        for article in articles[:15]:
            link_tag = article.select_one(SITE_CONFIG["link_selector"])
            if link_tag:
                href = link_tag.get("href")
                if href:
                    if not href.startswith("http"):
                        href = "https://www.ynet.co.il" + href
                    news_list.append(href)
        return news_list
    except Exception as e:
        print(f"❌ خطا در دریافت اخبار Ynet: {e}")
        return []

def extract_article_detail(url):
    try:
        response = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        
        # استفاده از سلکتورهای جدید برای تیتر و زیرتیتر
        title_tag = soup.select_one("#ArticleHeaderComponent > div.mainTitleWrapper > h1")
        title = title_tag.get_text(strip=True) if title_tag else "بدون تیتر"
        
        lead_tag = soup.select_one("#ArticleHeaderComponent > div.subTitleWrapper")
        lead = lead_tag.get_text(strip=True) if lead_tag else ""
        
        img_tag = soup.select_one("div.mainImage img, div.imageWrap img")
        img_url = img_tag.get("src") if img_tag else None
        if img_url and not img_url.startswith("http"):
            img_url = "https://www.ynet.co.il" + img_url
        
        body_paragraphs = soup.select("div.textWrap div.paragraphs p")
        full_text = " ".join([p.get_text(strip=True) for p in body_paragraphs[:3]])
        if not full_text:
            full_text = title + " " + lead
        
        return {
            "title": title,
            "lead": lead[:300],
            "img_url": img_url,
            "full_text": full_text,
            "url": url
        }
    except Exception as e:
        print(f"❌ خطا در استخراج جزئیات خبر {url}: {e}")
        return None

# ========== ترجمه و ارسال به تلگرام ==========
def send_to_telegram(article):
    try:
        translator = GoogleTranslator(source='auto', target='fa')
        translated_title = translator.translate(article['title'])
        translated_lead = translator.translate(article['lead'])
        
        original_text = f"📰 {article['title']}\n{article['lead']}"
        translated_text = f"🇮🇷 ترجمه فارسی:\n{translated_title}\n{translated_lead}"
        final_caption = f"{original_text}\n\n{translated_text}\n\n#سیاسی"
        
    except Exception as e:
        print(f"⚠️ خطا در ترجمه: {e}")
        final_caption = f"📰 {article['title']}\n{article['lead']}\n\n#سیاسی"
    
    if article["img_url"]:
        send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": CHAT_ID,
            "photo": article["img_url"],
            "caption": final_caption[:1024],
            "parse_mode": "HTML"
        }
        response = requests.post(send_url, data=payload)
        if response.status_code != 200:
            print(f"❌ خطا در ارسال عکس: {response.text}")
    else:
        send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": final_caption[:4096],
            "parse_mode": "HTML"
        }
        response = requests.post(send_url, data=payload)
        if response.status_code != 200:
            print(f"❌ خطا در ارسال متن: {response.text}")
    
    sent_urls.add(article["url"])
    save_sent_urls(sent_urls)
    print(f"✅ خبر به تلگرام ارسال شد: {article['title']}")

# ========== اجرای یک‌باره ==========
def run_once():
    print("🚀 شروع خزش از Ynet...")
    article_links = fetch_ynet_news()
    print(f"📌 تعداد اخبار پیدا شده: {len(article_links)}")
    
    for link in article_links:
        if link in sent_urls:
            print(f"⏩ خبر تکراری: {link}")
            continue
        article_data = extract_article_detail(link)
        if article_data:
            send_to_telegram(article_data)
            time.sleep(3)
    
    print("✅ عملیات امروز انجام شد!")

if __name__ == "__main__":
    run_once()
