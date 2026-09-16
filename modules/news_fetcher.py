import requests
import urllib.parse
from config import NAVER_API_KEY_ID, NAVER_API_KEY

def fetch_latest_news(keyword, display=5):
    """
    네이버 뉴스 검색 API를 사용하여 특정 키워드의 최신 뉴스를 가져옵니다.
    """
    if not NAVER_API_KEY_ID or not NAVER_API_KEY:
        raise ValueError("NCP API 키가 설정되지 않았습니다.")

    enc_text = urllib.parse.quote(keyword)
    # NCP API HUB 검색 API 주소
    url = f"https://naverapihub.apigw.ntruss.com/search/v1/news?query={enc_text}&display={display}&sort=sim"
    
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_API_KEY_ID,
        "X-NCP-APIGW-API-KEY": NAVER_API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        news_items = []
        for item in data.get("items", []):
            news_items.append({
                "title": item["title"],
                "originallink": item["originallink"],
                "link": item["link"], # 네이버 뉴스 링크 또는 원문 링크
                "description": item["description"],
                "pubDate": item["pubDate"]
            })
        return news_items
    except Exception as e:
        print(f"[News Fetcher] 뉴스 수집 중 오류 발생: {e}")
        return []
