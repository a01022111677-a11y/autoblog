"""토스쇼핑 쉐어링크 OpenAPI 연동 모듈.

흐름 (https://sharelink-docs.toss.im 공식 문서 기준):
  1. POST https://oauth2.cert.toss.im/token (client_credentials) -> access_token
  2. GET  https://sharelink.toss.im/openapi/products/best-selling?size=30
  3. POST https://sharelink.toss.im/openapi/links {tacaItemId, publisherId} -> shortUrl
  4. shortUrl + 상품정보를 블로그 본문 사이사이에 1개씩 분산 삽입 (반드시 shortUrl 사용)

 필요 환경변수 (.env / Streamlit Secrets):
   TOSS_ACCESS_KEY    (Access Key)
   TOSS_SECRET_KEY    (Secret Key)
   TOSS_PUBLISHER_ID  (퍼블리셔 UUID)
"""
import time
import requests
import re
from collections import deque
import json as _json
import os as _os

TOKEN_URL = "https://oauth2.cert.toss.im/token"
API_BASE = "https://sharelink.toss.im/openapi"

_token_cache = {"token": None, "expires_at": 0}


def _proxies():
    """고정IP 프록시 경유 설정 (Streamlit Cloud처럼 IP 등록이 불가한 환경용)."""
    try:
        from config import TOSS_HTTPS_PROXY
        url = (TOSS_HTTPS_PROXY or "").strip()
    except Exception:
        url = ""
    if not url:
        return None
    return {"http": url, "https": url}


def _relay_cfg():
    """중계서버 설정. (url, secret) 또는 None."""
    try:
        from config import TOSS_RELAY_URL, TOSS_RELAY_SECRET
    except Exception:
        return None
    url = (TOSS_RELAY_URL or "").strip().rstrip("/")
    if not url:
        return None
    return (url, TOSS_RELAY_SECRET or "")


def use_relay():
    """중계 모드 여부 (UI 표시용)."""
    return _relay_cfg() is not None


def _relay_call(method, path, params=None, payload=None, timeout=40):
    base, secret = _relay_cfg()
    resp = requests.request(
        method, base + path, params=params, json=payload,
        headers={"X-Relay-Secret": secret}, timeout=timeout,
    )
    if resp.status_code == 401:
        raise RuntimeError("중계서버 인증 실패 (TOSS_RELAY_SECRET 확인 + 중계서버 실행 여부 확인)")
    if resp.status_code != 200:
        raise RuntimeError(f"중계서버 오류 {resp.status_code}: {resp.text[:200]}")
    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(f"중계서버 응답 파싱 실패: {resp.text[:200]}")
    if not data.get("ok"):
        raise RuntimeError(f"중계 실패: {data.get('error', '')[:300]}")
    return data.get("data")


def _get_access_token(access_key, secret_key):
    """client_credentials 방식으로 액세스 토큰 발급 (만료 60초 전 갱신)."""
    if not access_key or not secret_key:
        raise ValueError("토스 Access Key / Secret Key가 없습니다.")

    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": access_key,
            "client_secret": secret_key,
            "scope": "sharelink:read sharelink:write",
        },
        timeout=15,
        proxies=_proxies(),
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"토스 토큰 발급 실패: {data}")
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + int(data.get("expires_in", 31536000))
    return token


def fetch_best_selling(access_key, secret_key, size=30):
    """카테고리 구분 없이 지금 많이 팔리는 상품 목록 조회."""
    if _relay_cfg():
        return _relay_call("GET", "/toss/best-selling", params={"size": max(1, min(size, 100))}) or []
    token = _get_access_token(access_key, secret_key)
    resp = requests.get(
        f"{API_BASE}/products/best-selling",
        headers={"Authorization": f"Bearer {token}"},
        params={"size": max(1, min(size, 100))},
        timeout=15,
        proxies=_proxies(),
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("resultType") != "SUCCESS":
        raise RuntimeError(f"베스트 상품 조회 실패: {data}")
    return data.get("success", {}).get("items", [])


def fetch_today_deals(access_key, secret_key, size=10):
    """하루특가 상품 조회 (없으면 빈 리스트)."""
    if _relay_cfg():
        try:
            return _relay_call("GET", "/toss/today-deals", params={"size": max(1, min(size, 30))}) or []
        except Exception as e:
            print(f"[Toss] 하루특가 조회 실패 (무시): {e}")
            return []
    try:
        token = _get_access_token(access_key, secret_key)
        resp = requests.get(
            f"{API_BASE}/products/today-deals",
            headers={"Authorization": f"Bearer {token}"},
            params={"size": max(1, min(size, 30))},
            timeout=15,
            proxies=_proxies(),
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("resultType") != "SUCCESS":
            return []
        return data.get("success", {}).get("items", [])
    except Exception as e:
        print(f"[Toss] 하루특가 조회 실패 (무시): {e}")
        return []


def issue_sharelink(access_key, secret_key, publisher_id, taca_item_id):
    """tacaItemId + publisherId 로 추적 가능한 shortUrl 발급."""
    if _relay_cfg():
        data = _relay_call("POST", "/toss/links",
                           payload={"tacaItemId": int(taca_item_id), "publisherId": publisher_id}) or {}
        if not data.get("shortUrl"):
            raise RuntimeError(f"쉐어링크 발급 실패: {data}")
        return {"shortUrl": data.get("shortUrl"), "originUrl": data.get("originUrl")}
    if not publisher_id:
        raise ValueError("TOSS_PUBLISHER_ID가 없습니다.")
    token = _get_access_token(access_key, secret_key)
    resp = requests.post(
        f"{API_BASE}/links",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"tacaItemId": int(taca_item_id), "publisherId": publisher_id},
        timeout=15,
        proxies=_proxies(),
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("resultType") != "SUCCESS":
        raise RuntimeError(f"쉐어링크 발급 실패: {data}")
    success = data.get("success", {})
    return {
        "shortUrl": success.get("shortUrl"),
        "originUrl": success.get("originUrl"),
    }


# 최근 광고 상품 기억 파일 (재시작해도 같은 상품 무한 반복 방지)
_RECENT_FILE = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    ".toss_recent.json",
)
_RECENT_MAX = 30


def _load_recent_ids():
    try:
        with open(_RECENT_FILE, "r", encoding="utf-8") as f:
            data = _json.load(f)
        return [str(x) for x in data] if isinstance(data, list) else []
    except Exception:
        return []


def _save_recent_ids(ids):
    try:
        with open(_RECENT_FILE, "w", encoding="utf-8") as f:
            _json.dump([str(x) for x in ids[-_RECENT_MAX:]], f)
    except Exception as e:
        print(f"[Toss] 최근상품 기록 실패 (무시): {e}")


# 최근 광고에 쓴 상품 기억 (같은 상품 무한 반복 방지, 메모리+디스크)
_recent_product_ids = deque(_load_recent_ids(), maxlen=_RECENT_MAX)


def pick_relevant_products(keyword, products, top_n=3, blog_text="", gemini_api_key=None):
    """글 문맥(keyword + 본문 앞부분)과 가장 어울리는 상품 top_n개 선정.
    1순위: Gemini로 관련도 랭킹 (실패 시 폴백)
    폴백: 상품명 내 키워드 토큰 매칭 + 리뷰수/평점 + 품절 제외
    """
    if not products:
        return []
    # 품절 제외
    candidates = [p for p in products if not p.get("isSoldOut")]
    if not candidates:
        candidates = products
    top_n = max(1, min(top_n, len(candidates)))

    def _exclude_recent(cands):
        fresh = [p for p in cands if str(p.get("tacaItemId")) not in _recent_product_ids]
        return fresh if len(fresh) >= top_n else cands

    def _remember(picked):
        for p in picked:
            _recent_product_ids.append(str(p.get("tacaItemId")))
        _save_recent_ids(list(_recent_product_ids))

    candidates = _exclude_recent(candidates)

    # --- Gemini 랭킹 시도 ---
    if gemini_api_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_api_key)
            listing = "\n".join(
                f"{i}. {p.get('displayName','')[:60]} (리뷰 {p.get('reviewCount',0)}, 평점 {p.get('reviewScore','-')})"
                for i, p in enumerate(candidates[:30])
            )
            prompt = (
                f"블로그 주제: '{keyword}'\n"
                f"블로그 본문 발췌: {(blog_text or '')[:800]}\n\n"
                f"아래 토스쇼핑 베스트 상품 목록 중, 블로그 독자가 자연스럽게 클릭할 만한 "
                f"관련 상품 {top_n}개를 번호만 콤마로 답하세요. (예: 2,5,7)\n{listing}"
            )
            resp = client.models.generate_content(model="gemini-flash-latest", contents=prompt)
            nums = [int(n) for n in re.findall(r"\d+", resp.text or "") if int(n) < len(candidates)]
            picked = []
            for n in nums:
                if candidates[n] not in picked:
                    picked.append(candidates[n])
                if len(picked) >= top_n:
                    break
            if picked:
                _remember(picked)
                return picked
        except Exception as e:
            print(f"[Toss] Gemini 상품 매칭 실패, 폴백 사용: {e}")

    # --- 폴백: 키워드 토큰 매칭 ---
    tokens = [t for t in re.split(r"\s+", keyword or "") if len(t) >= 2]
    stop = {"핫이슈", "요약", "관련", "최신", "오늘", "속보"}
    tokens = [t for t in tokens if t not in stop]

    def score(p):
        name = p.get("displayName", "") or ""
        hit = sum(1 for t in tokens if t in name)
        import math
        pop = math.log10((p.get("reviewCount") or 0) + 10)
        rate = (p.get("reviewScore") or 0) / 5.0
        return (hit * 10 + pop + rate, (p.get("reviewCount") or 0))

    candidates.sort(key=score, reverse=True)
    picked = candidates[:top_n]
    _remember(picked)
    return picked


def get_toss_products_for_blog(keyword, blog_text="", count=3,
                               access_key=None, secret_key=None, publisher_id=None,
                               gemini_api_key=None):
    """베스트 조회 -> 문맥 매칭 -> 쉐어링크 발급까지 한번에. 실패해도 예외 대신 빈 리스트."""
    try:
        products = fetch_best_selling(access_key, secret_key, size=30)
        deals = fetch_today_deals(access_key, secret_key, size=10)
        seen = {p.get("tacaItemId") for p in products}
        for d in deals:
            if d.get("tacaItemId") not in seen:
                products.append(d)
        picked = pick_relevant_products(keyword, products, top_n=count,
                                        blog_text=blog_text, gemini_api_key=gemini_api_key)
        result = []
        for p in picked:
            try:
                link = issue_sharelink(access_key, secret_key, publisher_id, p["tacaItemId"])
                p = {**p, **link}
            except Exception as e:
                print(f"[Toss] 쉐어링크 발급 실패, 상품 제외 ({p.get('displayName')}): {e}")
                continue
            result.append(p)
        return result
    except Exception as e:
        print(f"[Toss] 상품 준비 중 오류 (블로그는 정상 생성됨): {e}")
        return []


def _fmt_price(n):
    try:
        return f"{int(n):,}원"
    except Exception:
        return "-"


def build_product_card(p):
    """상품 1개짜리 낱장 광고 카드 (본문 사이사이에 1개씩 삽입용).
    - 사진: 100~110px로 아담하고 깔끔하게 축소
    - 가격: 24~26px 대형 폰트로 시원하게 강조
    - 할인 전 가격: <s>취소선</s>으로 긋고 '❌ 정가 아닙니다' 세일즈 카피 적용
    - 할인율: 빨간색 강조 배지
    - 리뷰수/평점: 실구매자 인증 카피
    - 최저가 바로가기 버튼: 클릭 유도형 블루 버튼"""
    name = p.get("displayName", "토스쇼핑 추천 상품")[:60]
    url = p.get("shortUrl") or p.get("productUrl") or "https://sharelink.toss.im"
    thumb = p.get("thumbnailUrl")
    try:
        price = int(p.get("displayPrice") or 0)
    except Exception:
        price = 0
    try:
        orig = int(p.get("originalPrice") or 0)
    except Exception:
        orig = 0
    disc = p.get("discountRate") or 0
    score = p.get("reviewScore")
    cnt = p.get("reviewCount") or 0

    L = ['<div style="border: 2px solid #0064FF; padding: 16px; border-radius: 12px; text-align: left; margin: 24px auto; max-width: 420px; background-color: rgba(0, 100, 255, 0.02);">']
    L.append('<div style="font-size: 12px; color: #0064FF; font-weight: bold; margin-bottom: 6px;">🛒 [카레의 토스쇼핑 핫딜 추천]</div>')
    
    if thumb:
        # 사진 크기 대폭 축소 (100px) 및 중앙 배치
        L.append(f'<div style="text-align: center; margin: 6px 0;"><img src="{thumb}" width="100" style="width: 100px; max-width: 100px; height: auto; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.15);" /></div>')
    
    L.append(f'<div style="font-size: 15px; font-weight: bold; margin-bottom: 6px; line-height: 1.4;">📦 {name}</div>')
    
    # 가격 및 취소선 영역
    if orig > 0 and price > 0 and orig > price:
        L.append(f'<div style="margin: 4px 0;">')
        L.append(f'  <span style="color: #888888; font-size: 14px; text-decoration: line-through;">기존 정가 {_fmt_price(orig)}</span>')
        if disc:
            L.append(f'  <span style="background-color: #ffe3e3; color: #E02020; font-weight: 800; font-size: 13px; padding: 2px 6px; border-radius: 4px; margin-left: 6px;">{disc}% 🔻 특가할인</span>')
        L.append(f'</div>')
        L.append(f'<div style="margin: 4px 0;">')
        L.append(f'  <span style="font-size: 13px; color: #444444; font-weight: bold;">🔥 오늘만 특가 👉 </span>')
        L.append(f'  <span style="font-size: 26px; font-weight: 900; color: #E02020; letter-spacing: -0.5px;">{_fmt_price(price)}</span>')
        L.append(f'</div>')
    elif price > 0:
        L.append(f'<div style="margin: 4px 0;">')
        L.append(f'  <span style="font-size: 13px; color: #444444; font-weight: bold;">🔥 단독 특가 👉 </span>')
        L.append(f'  <span style="font-size: 26px; font-weight: 900; color: #E02020; letter-spacing: -0.5px;">{_fmt_price(price)}</span>')
        L.append(f'</div>')

    # 리뷰 및 평점 카피
    if score and cnt:
        L.append(f'<div style="font-size: 13px; color: #555555; margin: 6px 0;">⭐ 실구매 평점 <b>{score}점</b> · 리뷰 <b>{cnt:,}개</b> 돌파 대란템!</div>')
    elif cnt:
        L.append(f'<div style="font-size: 13px; color: #555555; margin: 6px 0;">⭐ 실구매 리뷰 <b>{cnt:,}개</b> 돌파 인기템!</div>')

    # 웹 최저가 비교선 (있을 때만)
    _cmp = ""
    if p.get("web_lowest"):
        try:
            from modules.price_research import format_compare as _fmt_cmp
            _cmp = _fmt_cmp(price, p.get("web_lowest"), p.get("web_mall", ""))
        except Exception:
            _cmp = ""
    if _cmp:
        L.append(f'<div style="font-size: 12px; color: #2b8a3e; margin: 4px 0;">{_cmp}</div>')

    # 구매 버튼 (눈에 띄는 파란색 버튼)
    L.append(f'<div style="text-align: center; margin-top: 12px;">')
    L.append(f'  <a href="{url}" style="display: inline-block; background-color: #0064FF; color: #ffffff; padding: 10px 22px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 14px; box-shadow: 0 2px 4px rgba(0,100,255,0.3);">'
             f'👉 토스쇼핑에서 할인가로 득템하기</a>')
    L.append(f'</div>')
    L.append("</div>")
    return "\n".join(L)


def build_disclosure(has_compare=False):
    """글 맨 끝 대가성 문구 (필수)."""
    lines = ["\n\n---\n"]
    if has_compare:
        lines.append("> 🔎 가격 비교는 AI 웹 검색 기준 참고용이며 옵션·배송비·시점에 따라 다를 수 있어요.\n")
    lines.append(
        "> 📢 <b>이 포스팅은 토스쇼핑 쉐어링크를 포함하고 있어요.</b> "
        "링크를 통해 구매하시면 카레에게 소정의 수수료가 지급됩니다. (구매자님 추가 비용 없음 🙏)"
    )
    return "\n".join(lines)


def insert_inline_ads(blog_content, products):
    """본문 속 [[TOSS_AD_1]]… 토큰 자리에 상품 카드를 1개씩 치환.
    토큰이 없거나 누락된 경우, 본문 문단/소제목 사이에 1개씩 고르게 분산 삽입!
    (광고가 뭉치지 않고 본문 사이사이에 1개씩 자연스럽게 분배)"""
    if not products:
        return blog_content, []

    content = blog_content
    leftover = []
    
    # 1. AI가 명시적으로 넣은 토큰 먼저 치환
    for i, p in enumerate(products, 1):
        placed = False
        for token in (f"[[TOSS_AD_{i}]]", f"`[[TOSS_AD_{i}]]`"):
            if token in content:
                content = content.replace(token, "\n\n" + build_product_card(p) + "\n\n")
                placed = True
        if not placed:
            leftover.append(p)

    # 2. 토큰이 없어서 남은 상품이 있다면, 본문 사이사이에 1개씩 고르게 분산 배치
    if leftover:
        # 소제목 태그(<h3 또는 ##) 기준으로 본문 나누기 시도
        parts = re.split(r'(\n(?:<h3|##)\b[^\n]*\n)', content)
        if len(parts) > 1:
            new_content = ""
            ad_idx = 0
            for part in parts:
                new_content += part
                if (part.startswith("\n<h3") or part.startswith("\n##")) and ad_idx < len(leftover):
                    new_content += "\n\n" + build_product_card(leftover[ad_idx]) + "\n\n"
                    ad_idx += 1
            while ad_idx < len(leftover):
                new_content += "\n\n" + build_product_card(leftover[ad_idx]) + "\n\n"
                ad_idx += 1
            content = new_content
            leftover = []
        else:
            # 소제목이 없을 경우 단락별로 1개씩 분산 배치
            paragraphs = content.split("\n\n")
            step = max(1, len(paragraphs) // (len(leftover) + 1))
            new_paras = []
            ad_idx = 0
            for i, p_text in enumerate(paragraphs):
                new_paras.append(p_text)
                if i > 0 and i % step == 0 and ad_idx < len(leftover):
                    new_paras.append(build_product_card(leftover[ad_idx]))
                    ad_idx += 1
            while ad_idx < len(leftover):
                new_paras.append(build_product_card(leftover[ad_idx]))
                ad_idx += 1
            content = "\n\n".join(new_paras)
            leftover = []

    return content, leftover


def append_toss_footer(blog_content, keyword="", products=None,
                       access_key=None, secret_key=None, publisher_id=None,
                       gemini_api_key=None, count=3):
    """토스 광고 삽입 (본문 사이사이 1개씩 고르게 분산 배치 + 대가성 문구).
    products가 주어지면 API 호출 생략."""
    if not blog_content:
        return blog_content
    if "토스쇼핑 쉐어링크" in blog_content or "toss.im/_m/" in blog_content:
        return blog_content  # 중복 삽입 방지
    if products is None:
        _has_keys = bool(access_key and secret_key and publisher_id)
        if not (_has_keys or use_relay()):
            return blog_content  # 키도 중계도 없으면 조용히 패스
        products = get_toss_products_for_blog(
            keyword, blog_text=blog_content, count=count,
            access_key=access_key, secret_key=secret_key,
            publisher_id=publisher_id, gemini_api_key=gemini_api_key,
        )
    if not products:
        return blog_content
    if gemini_api_key:
        # Gemini 웹 그라운딩으로 상품별 온라인 최저가 조사 (실패분은 비교줄 없이 진행)
        try:
            from modules.price_research import research_lowest_price
            from config import GEMINI_MODEL as _model
            for p in products:
                if not p.get("displayPrice"):
                    continue
                _wp, _wm, _wu = research_lowest_price(
                    p.get("displayName", ""), gemini_api_key,
                    model=_model or "gemini-flash-latest")
                if _wp:
                    p["web_lowest"] = _wp
                    p["web_mall"] = _wm
        except Exception as e:
            print(f"[Toss] 가격 리서치 생략: {e}")
    content, leftover = insert_inline_ads(blog_content, products)
    has_compare = any(p.get("web_lowest") for p in products)
    for p in leftover:
        content += "\n\n" + build_product_card(p)
    content += build_disclosure(has_compare=has_compare)
    return content
