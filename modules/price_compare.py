"""네이버 쇼핑 API 가격 비교 모듈.

이미 보유한 NCP API 키 그대로 사용 (추가 발급 불필요):
  GET https://naverapihub.apigw.ntruss.com/search/v1/shop?query=...&display=5&sort=sim

토스 박스에 "타사 최저가 vs 토스" 한 줄을 붙여 토스 상품을 부각시킨다.
매칭은 상품명 기준이므로 참고용 문구를 함께 둔다.
"""
import re
import urllib.parse
import requests


def _clean(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return " ".join(text.split())


def _short_query(name, max_len=30):
    """상품명에서 검색용 핵심어만 추출 (너무 길면 뒷부분 절단)."""
    name = _clean(name)
    # 용량/수량 꼬리표는 검색에 방해되므로 뒤쪽부터 과하게 길면 자름
    return name[:max_len].strip()


def get_naver_lowest(query, api_key_id, api_key, display=5, timeout=10):
    """네이버 쇼핑 최저가 조회. (lprice:int|None, mall:str|None) 반환. 실패 시 (None, None)."""
    if not (api_key_id and api_key and query):
        return (None, None)
    try:
        enc = urllib.parse.quote(_short_query(query))
        url = (
            "https://naverapihub.apigw.ntruss.com/search/v1/shop"
            f"?query={enc}&display={max(1, min(display, 10))}&sort=sim"
        )
        resp = requests.get(url, headers={
            "X-NCP-APIGW-API-KEY-ID": api_key_id,
            "X-NCP-APIGW-API-KEY": api_key,
        }, timeout=timeout)
        resp.raise_for_status()
        items = resp.json().get("items", []) or []
        best = None
        for it in items:
            try:
                price = int(it.get("lprice") or 0)
            except Exception:
                continue
            if price <= 0:
                continue
            if best is None or price < best[0]:
                best = (price, it.get("mallName", "") or "", _clean(it.get("title", "")))
        if not best:
            return (None, None)
        return (best[0], best[1])
    except Exception as e:
        print(f"[PriceCompare] 네이버 쇼핑 조회 실패 ({query[:20]}): {e}")
        return (None, None)


def compare_line(toss_price, naver_price, naver_mall=""):
    """푸터용 비교 한 줄. 토스가 쌀 때만 절약액 강조, 아니면 중립 참고 표시."""
    try:
        t = int(toss_price or 0)
        n = int(naver_price or 0)
    except Exception:
        return ""
    if t <= 0 or n <= 0:
        return ""
    mall = f"({naver_mall})" if naver_mall else ""
    if t < n:
        return f"🔎 타사 최저가 {n:,}원{mall} vs <b>토스 {t:,}원 → {n - t:,}원 절약✨</b>"
    if t == n:
        return f"🔎 타사 최저가 {n:,}원{mall} vs <b>토스 동가👍</b>"
    return f"🔎 타사 최저가 참고: {n:,}원{mall}"
