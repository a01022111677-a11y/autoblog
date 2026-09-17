import os
from dotenv import load_dotenv

# .env 파일 로드 (로컬 환경 변수 설정)
load_dotenv()


def _get_key(name, default=None):
    """우선순위: st.secrets (Streamlit Cloud) > 환경변수(.env/시스템) > default.

    streamlit이 없거나 secrets가 없어도 크래시 없이 동작한다.
    """
    # 1. Streamlit Secrets (클라우드 배포용)
    try:
        import streamlit as st
        try:
            val = st.secrets.get(name, None)
            if val not in (None, ""):
                return val
        except Exception:
            pass
    except Exception:
        pass
    # 2. 환경변수
    return os.getenv(name, default)


def _get_int(name, default):
    try:
        return int(_get_key(name, str(default)))
    except Exception:
        return default


def _get_bool(name, default):
    val = _get_key(name, None)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")


# Naver API HUB (NCP) Settings
NAVER_API_KEY_ID = _get_key("NAVER_API_KEY_ID")
NAVER_API_KEY = _get_key("NAVER_API_KEY")

# Gemini API Settings
GEMINI_API_KEY = _get_key("GEMINI_API_KEY")
# 1순위 모델 (Secrets에서 GEMINI_MODEL로 교체 가능, 미지정 시 체인 기본값 사용)
GEMINI_MODEL = _get_key("GEMINI_MODEL", None)

# Naver Blog Settings
NAVER_BLOG_ID = _get_key("NAVER_BLOG_ID")
NAVER_BLOG_TOKEN = _get_key("NAVER_BLOG_TOKEN")

# App Settings
SEARCH_KEYWORD = _get_key("SEARCH_KEYWORD", "경제")

# Toss Shopping Sharelink Settings (https://sharelink.toss.im)
# "xxx" 같은 플레이스홀더는 미입력으로 간주 (실제 키를 넣기 전까지 토스 기능 off)
def _get_toss_key(name):
    val = _get_key(name, None)
    if isinstance(val, str) and val.strip().lower() in ("", "xxx", "your-key-here", "changeme"):
        return None
    return val


TOSS_ACCESS_KEY = _get_toss_key("TOSS_ACCESS_KEY")
TOSS_SECRET_KEY = _get_toss_key("TOSS_SECRET_KEY")
TOSS_PUBLISHER_ID = _get_toss_key("TOSS_PUBLISHER_ID")
TOSS_PRODUCT_COUNT = _get_int("TOSS_PRODUCT_COUNT", 3)
# 고정IP 프록시 (Streamlit Cloud처럼 출발지 IP 등록이 불가한 환경용)
# 예: TOSS_HTTPS_PROXY = "http://user:pass@proxy-host:8080" (미설정 시 직접 연결)
TOSS_HTTPS_PROXY = _get_key("TOSS_HTTPS_PROXY", None)

# 중계서버 모드 (집PC 등 고정IP 머신에서 relay_server.py 실행 시)
# Cloud Secrets에만 넣으면 된다 (토스 키는 중계서버 쪽 .env에만 있으면 됨)
TOSS_RELAY_URL = _get_key("TOSS_RELAY_URL", None)
TOSS_RELAY_SECRET = _get_key("TOSS_RELAY_SECRET", None)
# 키 3종 OR 중계서버 설정이 있으면 활성화. Secrets에 TOSS_ENABLED=false를 넣으면 강제 비활성화.
TOSS_ENABLED = _get_bool(
    "TOSS_ENABLED",
    bool((TOSS_ACCESS_KEY and TOSS_SECRET_KEY and TOSS_PUBLISHER_ID) or TOSS_RELAY_URL),
)
