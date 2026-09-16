import streamlit as st
import time
import datetime
import re
import os

# 모듈 임포트
from config import NAVER_API_KEY_ID, NAVER_API_KEY, GEMINI_API_KEY, SEARCH_KEYWORD
from modules.news_fetcher import fetch_latest_news
from modules.content_extractor import extract_contents_from_news_items
from modules.synthesizer import synthesize_blog_post
from modules.publisher import publish_to_naver_blog

# 페이지 설정
st.set_page_config(page_title="AutoBlog Web", page_icon="📝", layout="centered")

st.title("📝 AutoBlog 자동 포스팅 시스템")
st.markdown("네이버 뉴스 검색과 Gemini AI를 활용하여 팩트 기반의 블로그 글을 자동으로 생성합니다.")

# 사이드바 설정 (환경 변수 상태 및 키워드 설정)
with st.sidebar:
    st.header("⚙️ 설정 (Settings)")
    
    # 키워드 입력
    keyword_input = st.text_input("검색 키워드", value=SEARCH_KEYWORD)
    
    st.divider()
    st.subheader("🔑 API 연동 상태")
    st.write("🟢 네이버 API" if NAVER_API_KEY_ID else "🔴 네이버 API (키 필요)")
    st.write("🟢 Gemini AI" if GEMINI_API_KEY else "🔴 Gemini AI (키 필요)")

# 메인 화면
if st.button("🚀 블로그 글 생성 시작", type="primary", use_container_width=True):
    if not NAVER_API_KEY_ID or not GEMINI_API_KEY:
        st.error("API 키가 설정되지 않았습니다. .env 파일을 확인해주세요!")
        st.stop()
        
    st.divider()
    
    # 진행 상태 표시 (스피너 및 상태 텍스트)
    with st.status("로봇이 열심히 일하고 있습니다...", expanded=True) as status:
        # 1. 뉴스 검색
        st.write(f"🔍 '{keyword_input}' 키워드로 최신 뉴스를 검색합니다...")
        news_items = fetch_latest_news(keyword_input, display=5)
        if not news_items:
            status.update(label="뉴스 검색 실패", state="error")
            st.stop()
            
        # 2. 본문 추출
        st.write("📰 뉴스 기사 원문을 추출하고 읽어들이는 중...")
        news_items_with_content = extract_contents_from_news_items(news_items)
        if not news_items_with_content:
            status.update(label="본문 추출 실패", state="error")
            st.stop()
            
        # 3. AI 글 생성
        st.write("🤖 Gemini AI가 글을 요약하고 종합적인 블로그 포스트를 작성 중입니다...")
        blog_post_content = synthesize_blog_post(news_items_with_content, keyword_input)
        if not blog_post_content:
            status.update(label="AI 글 생성 실패", state="error")
            st.stop()
            
        # 4. 파일 저장 처리
        st.write("💾 완성된 글을 파일로 저장하는 중...")
        title_match = re.search(r'^#\s+(.*)', blog_post_content, re.MULTILINE)
        if title_match:
            post_title = title_match.group(1).strip()
        else:
            post_title = f"[{datetime.datetime.now().strftime('%Y년 %m월 %d일')}] {keyword_input} 관련 최신 뉴스 종합"
            
        publish_to_naver_blog(post_title, blog_post_content)
        
        status.update(label="블로그 포스트 생성 완료!", state="complete", expanded=False)

    st.success("작업이 성공적으로 완료되었습니다!")
    
    # 결과물 출력 (탭으로 구성하여 UI 깔끔하게)
    tab1, tab2 = st.tabs(["📝 미리보기 (Preview)", "📜 마크다운 원문 (Raw Markdown)"])
    
    with tab1:
        st.markdown(blog_post_content)
        
    with tab2:
        st.code(blog_post_content, language='markdown')
        
    # 다운로드 버튼
    st.download_button(
        label="📥 Markdown 파일로 다운로드",
        data=blog_post_content,
        file_name=f"{keyword_input}_블로그포스트.md",
        mime="text/markdown"
    )
