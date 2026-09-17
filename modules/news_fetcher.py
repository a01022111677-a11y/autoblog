import requests
import urllib.parse
import random
import re
from config import NAVER_API_KEY_ID as _CFG_ID, NAVER_API_KEY as _CFG_KEY

def _clean_title(t):
    return re.sub(r'<[^>]+>', '', t or '').strip()

def fetch_latest_news(keyword, display=5, api_key_id=None, api_key=None, exclude_titles=None):
    """
    네이버 뉴스 검색 API를 사용하여 특정 키워드의 최신 뉴스를 가져옵니다.
    api_key_id/api_key가 주어지면 사이드바 입력값을 우선 사용 (Streamlit Cloud 대응).
    같은 주제 반복 생성 시 매번 똑같은 기사가 잡히지 않도록 2배로 가져와
    최근 사용 제목(exclude_titles)을 제외한 뒤 랜덤 샘플링합니다.
    """
    key_id = (api_key_id or _CFG_ID or "").strip() if isinstance((api_key_id or _CFG_ID), str) else (api_key_id or _CFG_ID)
    key = (api_key or _CFG_KEY or "").strip() if isinstance((api_key or _CFG_KEY), str) else (api_key or _CFG_KEY)
    if not key_id or not key:
        raise ValueError("NCP API 키가 설정되지 않았습니다.")

    enc_text = urllib.parse.quote(keyword)
    
    # 후보 풀 확보를 위해 2배로 수집
    fetch_n = max(display * 2, 10)
    # 1. 정확도순(sim)으로 깊이 있는 기사 수집
    url_sim = f"https://naverapihub.apigw.ntruss.com/search/v1/news?query={enc_text}&display={fetch_n}&sort=sim"
    # 2. 최신순(date)으로 따끈따끈한 속보 수집
    url_date = f"https://naverapihub.apigw.ntruss.com/search/v1/news?query={enc_text}&display={fetch_n}&sort=date"
    
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
            # 중복 기사 제거 (키가 없어도 죽지 않게 .get 사용)
            link = item.get("originallink") or item.get("link")
            if not link or link in seen_links:
                continue
            seen_links.add(link)
            
            news_items.append({
                "title": item.get("title", ""),
                "originallink": item.get("originallink", ""),
                "link": item.get("link", ""),
                "description": item.get("description", ""),
                "pubDate": item.get("pubDate", "")
            })
        
        # 최근 사용 기사 제외 (개수가 모자라면 중복 감수하고 원본 유지)
        if exclude_titles:
            _ex = {_clean_title(t) for t in exclude_titles}
            _fresh = [n for n in news_items if _clean_title(n.get("title", "")) not in _ex]
            if len(_fresh) >= display:
                news_items = _fresh
        
        # 후보가 많으면 랜덤 샘플링 (매번 다른 조합)
        if len(news_items) > display:
            news_items = random.sample(news_items, display)
            
        return news_items
    except Exception as e:
        print(f"[News Fetcher] 뉴스 수집 중 오류 발생: {e}")
        return []
