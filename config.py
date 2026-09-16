import os
from dotenv import load_dotenv

# .env 파일 로드 (로컬 환경 변수 설정)
load_dotenv()

# Naver API HUB (NCP) Settings
NAVER_API_KEY_ID = os.getenv("NAVER_API_KEY_ID")
NAVER_API_KEY = os.getenv("NAVER_API_KEY")

# Gemini API Settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Naver Blog Settings
NAVER_BLOG_ID = os.getenv("NAVER_BLOG_ID")
NAVER_BLOG_TOKEN = os.getenv("NAVER_BLOG_TOKEN")

# App Settings
SEARCH_KEYWORD = os.getenv("SEARCH_KEYWORD", "경제")
