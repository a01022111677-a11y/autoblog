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

# Naver Blog Settings
NAVER_BLOG_ID = _get_key("NAVER_BLOG_ID")
NAVER_BLOG_TOKEN = _get_key("NAVER_BLOG_TOKEN")

# App Settings
SEARCH_KEYWORD = _get_key("SEARCH_KEYWORD", "경제")

# Toss Shopping Sharelink Settings (https://sharelink.toss.im)
TOSS_ACCESS_KEY = _get_key("TOSS_ACCESS_KEY")
TOSS_SECRET_KEY = _get_key("TOSS_SECRET_KEY")
TOSS_PUBLISHER_ID = _get_key("TOSS_PUBLISHER_ID")
TOSS_PRODUCT_COUNT = _get_int("TOSS_PRODUCT_COUNT", 3)
# 기본은 키 3개가 다 있을 때 자동 삽입. Secrets에 TOSS_ENABLED=false를 넣으면 강제 비활성화.
TOSS_ENABLED = _get_bool(
    "TOSS_ENABLED",
    bool(TOSS_ACCESS_KEY and TOSS_SECRET_KEY and TOSS_PUBLISHER_ID),
)
