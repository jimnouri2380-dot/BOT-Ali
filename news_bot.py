import requests
from bs4 import BeautifulSoup
import time
import os
import json

# ========== گرفتن توکن و چت آیدی از Secrets گیت‌هاب ==========
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ========== مشخصات سایت تسنیم - بخش سیاسی (آدرس اصلاح شده) ==========
SITE_CONFIG = {
    "name": "تسنیم - سیاسی",
    "url": "https://www.tasnimnews.com/fa/service/politics",  # آدرس درست و زنده
    "article_selector": "div.item",  # سلکتور هر خبر در صفحه جدید
    "link_selector": "div.item a",   # سلکتور لینک خبر
    "title_selector": "h1.entry-title",
    "lead_selector": "div.summary p, div.lead p",
    "image_selector": "div.article-image img",
    "body_selector": "div.article-body p"
}

# ========== مدیریت خبرهای تکراری با فایل کش ==========
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

# ========== استخراج اخبار از تسنیم ==========
def fetch_tasnim_news():
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
                        href = "https://www.tasnimnews.com" + href
                    news_list.append(href)
        return news_list
    except Exception as e:
        print(f"❌ خطا در دریافت اخبار تسنیم: {e}")
        return []

def extract_article_detail(url):
    try:
        response = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        
        title_tag = soup.select_one("h1.entry-title")
        title = title_tag.get_text(strip=True) if title_tag else "بدون تیتر"
        
        lead_tag = soup.select_one("div.summary p") or soup.select_one("div.lead p")
        lead = lead_tag.get_text(strip=True) if lead_tag else ""
        
        img_tag = soup.select_one("div.article-image img")
        img_url = img_tag.get("src") if img_tag else None
        if img_url and not img_url.startswith("http"):
            img_url = "https://www.tasnimnews.com" + img_url
        
        body_paragraphs = soup.select("div.article-body p")
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

# ========== ارسال به تلگرام ==========
def send_to_telegram(article):
    original_text = f"📰 {article['title']}\n{article['lead']}"
    full_text = article["full_text"][:500]
    final_caption = f"{original_text}\n\nمتن کامل:\n{full_text}\n\n#سیاسی"
    
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
    print("🚀 شروع خزش از تسنیم...")
    article_links = fetch_tasnim_news()
    print(f"📌 تعداد اخبار پیدا شده: {len(article_links)}")
    
    for link in article_links:
        if link in sent_urls:
            print(f"⏩ خبر تکراری: {link}")
            continue
        article_data = extract_article_detail(link)
        if article_data:
            send_to_telegram(article_data)
            time.sleep(2)
    
    print("✅ عملیات امروز انجام شد!")

if __name__ == "__main__":
    run_once()
