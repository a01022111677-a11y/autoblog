import requests
import urllib.parse
from config import NAVER_API_KEY_ID as _CFG_ID, NAVER_API_KEY as _CFG_KEY

def fetch_latest_news(keyword, display=5, api_key_id=None, api_key=None):
    """
    네이버 뉴스 검색 API를 사용하여 특정 키워드의 최신 뉴스를 가져옵니다.
    api_key_id/api_key가 주어지면 사이드바 입력값을 우선 사용 (Streamlit Cloud 대응).
    """
    key_id = (api_key_id or _CFG_ID or "").strip() if isinstance((api_key_id or _CFG_ID), str) else (api_key_id or _CFG_ID)
    key = (api_key or _CFG_KEY or "").strip() if isinstance((api_key or _CFG_KEY), str) else (api_key or _CFG_KEY)
    if not key_id or not key:
        raise ValueError("NCP API 키가 설정되지 않았습니다.")

    enc_text = urllib.parse.quote(keyword)
    
    # 1. 정확도순(sim)으로 깊이 있는 기사 수집
    url_sim = f"https://naverapihub.apigw.ntruss.com/search/v1/news?query={enc_text}&display={display}&sort=sim"
    # 2. 최신순(date)으로 따끈따끈한 속보 수집
    url_date = f"https://naverapihub.apigw.ntruss.com/search/v1/news?query={enc_text}&display={display}&sort=date"
    
    headers = {
        "X-NCP-APIGW-API-KEY-ID": key_id,
        "X-NCP-APIGW-API-KEY": key
    }
    
    try:
        # 두 번의 API 호출 후 결과 합치기
        resp_sim = requests.get(url_sim, headers=headers).json()
        resp_date = requests.get(url_date, headers=headers).json()
        
        all_items = resp_sim.get("items", []) + resp_date.get("items", [])
        
        news_items = []
        seen_links = set()
        
        for item in all_items:
            # 중복 기사 제거
            link = item["originallink"] or item["link"]
            if link in seen_links:
                continue
            seen_links.add(link)
            
            news_items.append({
                "title": item["title"],
                "originallink": item["originallink"],
                "link": item["link"],
                "description": item["description"],
                "pubDate": item["pubDate"]
            })
            
        return news_items
    except Exception as e:
        print(f"[News Fetcher] 뉴스 수집 중 오류 발생: {e}")
        return []
