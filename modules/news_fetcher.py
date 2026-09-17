import requests
import urllib.parse
import random
import re
import xml.etree.ElementTree as ET
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
        fetch_latest_news.last_error = "NCP API 키 미설정"
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

        # 네이버 에러 페이로드는 즉시 노출 (빈 결과로 뭉개지 않게)
        for _resp in (resp_sim, resp_date):
            if isinstance(_resp, dict) and "error" in _resp:
                _err = _resp["error"] or {}
                raise RuntimeError(
                    f"네이버 API 오류 { _err.get('errorCode', '')}: {_err.get('message', '')}".strip()
                )
        
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

        if not news_items:
            fetch_latest_news.last_error = "검색 응답 0건 (할당량/키 권한 확인)"
        else:
            fetch_latest_news.last_error = ""
            fetch_latest_news.last_source = "naver"
        return news_items
    except Exception as e:
        fetch_latest_news.last_error = str(e)[:300]
        print(f"[News Fetcher] 네이버 수집 중 오류 발생: {e}")
        return []


def _fetch_google_rss(keyword, display=5, exclude_titles=None):
    """Google News RSS 폴백 (키 불필요). 네이버 Hub 장애 시에도 생성 가능."""
    try:
        enc = urllib.parse.quote(keyword)
        url = (f"https://news.google.com/rss/search?q={enc}&hl=ko&gl=KR&ceid=KR:ko")
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = []
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            desc = re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()
            pub = (it.findtext("pubDate") or "").strip()
            if not title or not link:
                continue
            # 구글 리다이렉트 추적용 원본도 함께 보관
            src = ""
            m = re.search(r"출처[:：]\s*(.+)$", desc)
            if m:
                src = m.group(1).strip()
            items.append({
                "title": title,
                "originallink": link,
                "link": link,
                "description": (src + " " + desc)[:300] if src else desc[:300],
                "pubDate": pub,
                # 구글 리다이렉트는 정적 추출 불가 → 제목+요약을 본문 대용으로 사용
                "content_hint": f"{title}. {desc[:500]}",
                "rss": True,
            })
            if len(items) >= max(display * 2, 10):
                break
        if exclude_titles:
            _ex = {_clean_title(t) for t in exclude_titles}
            _fresh = [n for n in items if _clean_title(n.get("title", "")) not in _ex]
            if len(_fresh) >= display:
                items = _fresh
        if len(items) > display:
            items = random.sample(items, display)
        if items:
            fetch_latest_news.last_source = "google-rss"
            fetch_latest_news.last_error = ""
        return items
    except Exception as e:
        print(f"[News Fetcher] RSS 수집 중 오류 발생: {e}")
        return []


_orig_fetch_latest_news = fetch_latest_news


def fetch_latest_news(keyword, display=5, api_key_id=None, api_key=None, exclude_titles=None):
    """네이버 Hub 우선 → 실패 시 Google News RSS 자동 폴백."""
    items = _orig_fetch_latest_news(
        keyword, display=display, api_key_id=api_key_id,
        api_key=api_key, exclude_titles=exclude_titles)
    if items:
        return items
    print("[News Fetcher] 네이버 실패 → Google RSS 폴백 시도")
    return _fetch_google_rss(keyword, display=display, exclude_titles=exclude_titles)


fetch_latest_news.last_error = ""
fetch_latest_news.last_source = "naver"
