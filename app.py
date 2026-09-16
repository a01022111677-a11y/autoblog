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

# 사이드바 설정 (환경 변수 상태)
with st.sidebar:
    st.header("⚙️ 설정 (Settings)")
    st.subheader("🔑 API 연동 상태")
    st.write("🟢 네이버 API" if NAVER_API_KEY_ID else "🔴 네이버 API (키 필요)")
    st.write("🟢 Gemini AI" if GEMINI_API_KEY else "🔴 Gemini AI (키 필요)")

st.divider()

# 1. 키워드 직접 입력 영역
st.subheader("🔍 검색 키워드 직접 입력")
st.write("원하시는 키워드를 입력하세요. 띄어쓰기로 여러 개를 입력하시면(예: `삼성전자 애플 테슬라`) 해당 키워드들이 모두 포함된 핫한 기사를 찾아 종합해 줍니다!")

def on_keyword_change():
    if 'selected_topic' in st.session_state:
        del st.session_state['selected_topic']
        
keyword_input = st.text_input("키워드 입력 후 엔터(Enter)를 치세요", value=SEARCH_KEYWORD, on_change=on_keyword_change)

st.divider()

# 2. 핫이슈 빠른 선택 영역
st.subheader("📌 핫이슈 빠른 선택")
st.write("또는 아래의 주제 버튼을 누르면 해당 분야의 최신 뉴스를 자동으로 검색합니다.")

# 첫 번째 줄 버튼
cols1 = st.columns(4)
if cols1[0].button("🏠 부동산", use_container_width=True):
    st.session_state.selected_topic = "부동산 핫이슈"
if cols1[1].button("📈 경제/증권", use_container_width=True):
    st.session_state.selected_topic = "경제 증권 핫이슈"
if cols1[2].button("⚖️ 정치", use_container_width=True):
    st.session_state.selected_topic = "정치 핫이슈"
if cols1[3].button("👥 사회", use_container_width=True):
    st.session_state.selected_topic = "사회 핫이슈"

# 두 번째 줄 버튼
cols2 = st.columns(4)
if cols2[0].button("🧬 과학/IT", use_container_width=True):
    st.session_state.selected_topic = "과학 IT 핫이슈"
if cols2[1].button("🌍 세계/국제", use_container_width=True):
    st.session_state.selected_topic = "국제 핫이슈"
if cols2[2].button("🎤 연예", use_container_width=True):
    st.session_state.selected_topic = "연예계 핫이슈"
if cols2[3].button("⚽ 스포츠", use_container_width=True):
    st.session_state.selected_topic = "스포츠 핫이슈"

st.divider()

# 3. 실행 영역
target_keyword = st.session_state.get('selected_topic', keyword_input)

if 'selected_topic' in st.session_state:
    st.info(f"💡 현재 선택된 주제: **'{target_keyword}'**\n\n이 주제의 최신 뉴스를 바탕으로 블로그 글을 작성하시겠습니까?")
    run_button_text = "✅ 네, 블로그 글 작성 시작하기!"
else:
    st.info(f"💡 직접 입력한 키워드: **'{target_keyword}'**\n\n이 키워드에 대한 최신 뉴스를 긁어와 블로그 글을 씁니다.")
    run_button_text = f"🚀 '{target_keyword}'(으)로 블로그 글 생성 시작"

if st.button(run_button_text, type="primary", use_container_width=True):
    if not NAVER_API_KEY_ID or not GEMINI_API_KEY:
        st.error("API 키가 설정되지 않았습니다. 사이드바 설정을 확인해주세요!")
        st.stop()
        
    st.divider()
    
    # 진행 상태 표시 (스피너 및 상태 텍스트)
    with st.status("로봇이 열심히 일하고 있습니다...", expanded=True) as status:
        # 1. 뉴스 검색
        st.write(f"🔍 '{target_keyword}' 키워드로 최신 뉴스를 검색합니다...")
        news_items = fetch_latest_news(target_keyword, display=5)
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
        blog_post_content = synthesize_blog_post(news_items_with_content, target_keyword)
        if not blog_post_content:
            status.update(label="AI 글 생성 실패", state="error")
            st.stop()
            
        # 4. 완료 처리
        status.update(label="블로그 포스트 생성 완료!", state="complete", expanded=False)

    st.success("작업이 성공적으로 완료되었습니다!")
    
    # ------------------
    # 복사 버튼 컴포넌트 추가
    import streamlit.components.v1 as components
    import json
    
    safe_text = json.dumps(blog_post_content)
    copy_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    </head>
    <body style="margin: 0; padding: 0;">
        <button id="copyBtn" style="width: 100%; padding: 12px; background-color: #ff4b4b; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
            📋 블로그용 전체 복사하기 (디자인/서식 포함)
        </button>
        
        <script>
            const mdText = {safe_text};
            const htmlText = marked.parse(mdText);
            
            document.getElementById('copyBtn').addEventListener('click', () => {{
                // 색상, 배경색 등을 싹 빼고 '순수 HTML'만 복사하는 핵심 마법 🪄
                const listener = (e) => {{
                    e.clipboardData.setData('text/html', htmlText);
                    e.clipboardData.setData('text/plain', mdText);
                    e.preventDefault();
                }};
                
                document.addEventListener('copy', listener);
                document.execCommand('copy');
                document.removeEventListener('copy', listener);
                
                const btn = document.getElementById('copyBtn');
                btn.innerText = '✅ 복사 완료! 네이버 블로그에 바로 붙여넣기(Ctrl+V) 하세요!';
                btn.style.backgroundColor = '#28a745';
                
                setTimeout(() => {{
                    btn.innerText = '📋 블로그용 전체 복사하기 (디자인/서식 포함)';
                    btn.style.backgroundColor = '#ff4b4b';
                }}, 3000);
            }});
        </script>
    </body>
    </html>
    """
    components.html(copy_html, height=60)
    # ------------------
    
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
        file_name=f"{target_keyword}_블로그포스트.md",
        mime="text/markdown"
    )
