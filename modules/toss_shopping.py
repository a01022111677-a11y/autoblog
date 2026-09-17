"""토스쇼핑 쉐어링크 OpenAPI 연동 모듈.

흐름 (https://sharelink-docs.toss.im 공식 문서 기준):
  1. POST https://oauth2.cert.toss.im/token (client_credentials) -> access_token
  2. GET  https://sharelink.toss.im/openapi/products/best-selling?size=30
  3. POST https://sharelink.toss.im/openapi/links {tacaItemId, publisherId} -> shortUrl
  4. shortUrl + 상품정보를 블로그 하단 박스로 삽입 (반드시 shortUrl 사용)

 필요 환경변수 (.env):
   TOSS_ACCESS_KEY    (Access Key)
   TOSS_SECRET_KEY    (Secret Key)
   TOSS_PUBLISHER_ID  (퍼블리셔 UUID)

 Cloud 등 출발지 IP 등록이 불가한 환경에서는 집PC 중계서버 경유 가능:
   TOSS_RELAY_URL     (예: https://xxx.trycloudflare.com)
   TOSS_RELAY_SECRET  (중계서버 RELAY_SECRET과 동일한 값)
   → 설정 시 아래 함수들이 토스 직접 호출 대신 중계서버로 요청한다.
"""
import time
import requests

TOKEN_URL = "https://oauth2.cert.toss.im/token"
API_BASE = "https://sharelink.toss.im/openapi"

_token_cache = {"token": None, "expires_at": 0}


def _proxies():
    """고정IP 프록시 경유 설정 (Streamlit Cloud처럼 IP 등록이 불가한 환경용).
    Secrets/env에 TOSS_HTTPS_PROXY="http://user:pass@host:port" 형식으로 넣으면 사용.
    미설정 시 None (직접 연결).
    """
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
    """tacaItemId + publisherId 로 추적 가능한 shortUrl 발급. 반드시 이 URL을 게시해야 수익 집계됨.
    중계 모드에서는 중계서버의 키/UUID로 발급하므로 Cloud에 키가 없어도 된다."""
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
            resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            import re
            nums = [int(n) for n in re.findall(r"\d+", resp.text or "") if int(n) < len(candidates)]
            picked = []
            for n in nums:
                if candidates[n] not in picked:
                    picked.append(candidates[n])
                if len(picked) >= top_n:
                    break
            if picked:
                return picked
        except Exception as e:
            print(f"[Toss] Gemini 상품 매칭 실패, 폴백 사용: {e}")

    # --- 폴백: 키워드 토큰 매칭 ---
    import re
    tokens = [t for t in re.split(r"\s+", keyword or "") if len(t) >= 2]
    # '핫이슈' 같은 공통어 제거
    stop = {"핫이슈", "요약", "관련", "최신", "오늘", "속보"}
    tokens = [t for t in tokens if t not in stop]

    def score(p):
        name = p.get("displayName", "") or ""
        hit = sum(1 for t in tokens if t in name)
        # 리뷰 많은 순 가산 (로그 스케일)
        import math
        pop = math.log10((p.get("reviewCount") or 0) + 10)
        rate = (p.get("reviewScore") or 0) / 5.0
        return (hit * 10 + pop + rate, (p.get("reviewCount") or 0))

    candidates.sort(key=score, reverse=True)
    return candidates[:top_n]


def get_toss_products_for_blog(keyword, blog_text="", count=3,
                               access_key=None, secret_key=None, publisher_id=None,
                               gemini_api_key=None):
    """베스트 조회 -> 문맥 매칭 -> 쉐어링크 발급까지 한번에. 실패해도 예외 대신 빈 리스트."""
    try:
        products = fetch_best_selling(access_key, secret_key, size=30)
        # 하루특가도 섞어서 선택지 확대 (선택, 실패 무시)
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


def build_toss_footer(products, keyword=""):
    """블로그 하단에 붙일 토스쇼핑 박스 (마크다운+HTML). 대가성 문구 포함(필수)."""
    if not products:
        return ""
    lines = []
    lines.append("\n\n---\n")
    lines.append(
        '<div style="border: 2px solid #0064FF; padding: 16px; border-radius: 12px; text-align: left; margin: 24px 0;">'
    )
    title = f"🛒 <b>{keyword} 읽고 많이 찾는 토스쇼핑 베스트템</b>" if keyword else "🛒 <b>토스쇼핑 베스트템</b>"
    lines.append(title + "<br><br>")
    _has_cmp = False
    try:
        from modules.price_compare import compare_line as _cmpline
    except Exception:
        _cmpline = None
    for i, p in enumerate(products, 1):
        name = p.get("displayName", "토스쇼핑 상품")[:70]
        price = _fmt_price(p.get("displayPrice"))
        orig = p.get("originalPrice")
        disc = p.get("discountRate")
        price_txt = price
        if orig and disc:
            price_txt = f"{price} <s>{_fmt_price(orig)}</s> ({disc}%🔻)"
        score = p.get("reviewScore")
        cnt = p.get("reviewCount")
        meta = ""
        if score or cnt:
            meta = f" ⭐{score} ({cnt}개 리뷰)" if score and cnt else (f" ⭐{score}" if score else f" ({cnt}개 리뷰)")
        url = p.get("shortUrl") or p.get("productUrl") or "https://sharelink.toss.im"
        thumb = p.get("thumbnailUrl")
        if thumb:
            lines.append(f'<img src="{thumb}" width="120" style="border-radius:8px;" /><br>')
        lines.append(f"{i}. <b>{name}</b><br>💰 {price_txt}{meta}<br>")
        if _cmpline:
            try:
                _cmp = _cmpline(p.get("displayPrice"), p.get("naver_lowest"), p.get("naver_mall", ""))
            except Exception:
                _cmp = ""
            if _cmp:
                lines.append(_cmp + "<br>")
                _has_cmp = True
        lines.append(f'<a href="{url}"><b>👉 토스쇼핑에서 최저가 보러가기</b></a><br><br>')
    lines.append("</div>")
    if _has_cmp:
        lines.append("> 🔎 가격 비교는 상품명 기준 참고용이며 옵션·배송비에 따라 다를 수 있어요.")
    lines.append(
        "> 📢 <b>이 포스팅은 토스쇼핑 쉐어링크를 포함하고 있어요.</b> "
        "링크를 통해 구매하시면 카레에게 소정의 수수료가 지급됩니다. (구매자님 추가 비용 없음 🙏)"
    )
    return "\n".join(lines)


def append_toss_footer(blog_content, keyword="", products=None,
                       access_key=None, secret_key=None, publisher_id=None,
                       gemini_api_key=None, count=3,
                       naver_key_id=None, naver_key=None):
    """blog_content 하단에 토스 박스 추가. products가 주어지면 API 호출 생략.
    naver_key_id/key가 있으면 상품마다 네이버 쇼핑 최저가를 조회해 비교 한 줄을 붙인다."""
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
    if products and naver_key_id and naver_key:
        try:
            from modules.price_compare import get_naver_lowest
            for p in products:
                _np, _mall = get_naver_lowest(
                    p.get("displayName", ""), naver_key_id, naver_key)
                p["naver_lowest"] = _np
                p["naver_mall"] = _mall
        except Exception as e:
            print(f"[Toss] 가격 비교 생략: {e}")
    footer = build_toss_footer(products, keyword)
    return blog_content + footer if footer else blog_content
