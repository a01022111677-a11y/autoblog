"""Gemini 웹 그라운딩 가격 리서치 모듈.

네이버 쇼핑 검색 API가 2026-07-31에 공식 종료되어 대체 수단이다.
보유 중인 Gemini 키로 Google 검색 그라운딩을 켜고
상품의 온라인 최저가를 실시간 조사한다.

필요: GEMINI_API_KEY (그라운딩 호출은 일반 호출보다 토큰을 더 씀)
실패 시 (None, None) → 호출부는 비교줄 없이 정상 진행.
"""
import json
import re

# 할당량이 바닥나면(429) 같은 실행에서 남은 상품 호출을 생략해 낭비 방지
_quota_dead = False


def _extract_json(text):
    """펜스 블록 또는 본문에서 lowest_price/mall/url JSON 추출."""
    if not text:
        return {}
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    blob = m.group(1) if m else None
    if not blob:
        m2 = re.search(r"\{[^{}]*lowest_price[^{}]*\}", text, re.S)
        blob = m2.group(0) if m2 else None
    if not blob:
        return {}
    try:
        return json.loads(blob)
    except Exception:
        return {}


def research_lowest_price(product_name, gemini_api_key, model="gemini-3.6-flash", timeout_note=""):
    """웹 검색 그라운딩으로 동일 상품 온라인 최저가 조사.
    (lowest_price:int|None, mall:str|None, url:str|None) 반환.
    """
    if not (product_name and gemini_api_key):
        return (None, None, None)
    global _quota_dead
    if _quota_dead:
        return (None, None, None)
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=gemini_api_key)
        prompt = (
            f"상품명: '{product_name.strip()[:60]}'\n\n"
            "위 상품과 동일한 상품(동일 브랜드·용량·구성)을 판매하는 한국 온라인 쇼핑몰의 "
            "현재 최저가를 웹 검색으로 찾아줘. 배송비 제외 상품가 기준, 원(₩) 단위.\n"
            "반드시 답변 마지막에 아래 JSON 블록을 정확히 포함해:\n"
            '```json {"lowest_price": 19900, "mall": "쇼핑몰명", "url": "상품URL"} ```\n'
            "(lowest_price는 숫자만. 못 찾으면 null과 빈 문자열로)"
        )
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        data = _extract_json(getattr(resp, "text", "") or "")
        raw_price = data.get("lowest_price")
        try:
            price = int(raw_price) if raw_price not in (None, "") else None
        except Exception:
            price = None
        mall = (data.get("mall") or "").strip() or None
        url = (data.get("url") or "").strip() or None
        if not price:
            return (None, None, None)
        return (price, mall, url)
    except Exception as e:
        _msg = str(e)
        if "429" in _msg or "RESOURCE_EXHAUSTED" in _msg or "quota" in _msg.lower():
            _quota_dead = True
            print("[PriceResearch] 할당량 소진 — 남은 상품 리서치 생략")
        print(f"[PriceResearch] 리서치 실패 ({(product_name or '')[:20]}): {_msg[:200]}")
        return (None, None, None)


def format_compare(toss_price, web_price, mall=""):
    """푸터용 비교 한 줄. 토스가 쌀 때만 절약액 강조, 아니면 중립 참고 표시."""
    try:
        t = int(toss_price or 0)
        n = int(web_price or 0)
    except Exception:
        return ""
    if t <= 0 or n <= 0:
        return ""
    mall_txt = f"({mall})" if mall else ""
    if t < n:
        return f"🔎 웹 최저가 {n:,}원{mall_txt} vs <b>토스 {t:,}원 → {n - t:,}원 절약✨</b>"
    if t == n:
        return f"🔎 웹 최저가 {n:,}원{mall_txt} vs <b>토스 동가👍</b>"
    return f"🔎 웹 최저가 참고: {n:,}원{mall_txt}"
