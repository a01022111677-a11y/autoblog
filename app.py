import streamlit as st
import time
import datetime
import re
import os
import json

# 모듈 임포트
from config import (
    NAVER_API_KEY_ID, NAVER_API_KEY, GEMINI_API_KEY, SEARCH_KEYWORD,
    TOSS_ACCESS_KEY, TOSS_SECRET_KEY, TOSS_PUBLISHER_ID,
    TOSS_PRODUCT_COUNT, TOSS_ENABLED,
)
from modules.news_fetcher import fetch_latest_news
from modules.content_extractor import extract_contents_from_news_items
from modules.synthesizer import synthesize_blog_post, gemini_model_chain
from modules.toss_shopping import append_toss_footer, fetch_best_selling

# 페이지 설정 (와이드 모드로 변경)
st.set_page_config(page_title="AutoBlog Web", page_icon="📝", layout="wide")

# 세션 상태(보관함) 초기화
if 'history' not in st.session_state:
    st.session_state.history = []

# 좌측 API 연결 상태 뷰어 (키 값 노출 없음 — 상태 표시 전용)
with st.sidebar:
    st.header("🔌 API 연결 상태")
    st.write("🟢 네이버 뉴스" if (NAVER_API_KEY_ID and NAVER_API_KEY) else "🔴 네이버 뉴스 (Secrets 필요)")
    st.write("🟢 Gemini" if GEMINI_API_KEY else "🔴 Gemini (Secrets 필요)")
    st.write("🟢 토스쇼핑" if TOSS_ENABLED else "⚪ 토스쇼핑 (미사용)")
    st.divider()
    if st.button("🧪 실시간 연결 테스트", use_container_width=True):
        with st.spinner("테스트 중..."):
            try:
                if not (NAVER_API_KEY_ID and NAVER_API_KEY):
                    st.write("🔴 네이버: 키 없음")
                else:
                    _items = fetch_latest_news("테스트", display=1)
                    st.write(f"🟢 네이버: 정상 ({len(_items)}건)" if _items else "🟡 네이버: 응답 0건 (키/할당량 확인)")
            except Exception as e:
                st.write(f"🔴 네이버: 실패 ({str(e)[:120]})")
            try:
                if not GEMINI_API_KEY:
                    st.write("🔴 Gemini: 키 없음")
                else:
                    from google import genai as _genai
                    _gclient = _genai.Client(api_key=GEMINI_API_KEY)
                    _gok, _gerr = "", ""
                    for _m in gemini_model_chain():
                        try:
                            _r = _gclient.models.generate_content(model=_m, contents="ping")
                            if (_r.text or "").strip():
                                _gok = _m
                                break
                        except Exception as e:
                            _gerr = str(e)[:150]
                    st.write(f"🟢 Gemini: 정상 ({_gok})" if _gok else f"🔴 Gemini: 실패 ({_gerr})")
            except Exception as e:
                st.write(f"🔴 Gemini: 실패 ({str(e)[:120]})")
            try:
                if not TOSS_ENABLED:
                    st.write("⚪ 토스: 미사용 (키 3개 필요)")
                else:
                    _titems = fetch_best_selling(TOSS_ACCESS_KEY, TOSS_SECRET_KEY, size=1)
                    _tname = _titems[0].get("displayName", "")[:25] if _titems else ""
                    st.write(f"🟢 토스: 정상 ({_tname})" if _titems else "🟡 토스: 응답 0건")
            except Exception as e:
                st.write(f"🔴 토스: 실패 ({str(e)[:150]})")
    st.divider()
    st.info("💡 키 관리는 우측 하단 Secrets에서만. 여긴 상태 표시 전용입니다.")

def _attach_toss_footer(blog_content, keyword):
    """토스 설정이 켜져 있으면 베스트상품 박스를 하단에 삽입. 실패해도 원본 반환."""
    if not blog_content or not TOSS_ENABLED:
        return blog_content
    if not (TOSS_ACCESS_KEY and TOSS_SECRET_KEY and TOSS_PUBLISHER_ID):
        return blog_content
    try:
        with st.spinner("🛒 글 문맥에 맞는 토스쇼핑 베스트상품 찾는 중..."):
            return append_toss_footer(
                blog_content,
                keyword=keyword,
                access_key=TOSS_ACCESS_KEY,
                secret_key=TOSS_SECRET_KEY,
                publisher_id=TOSS_PUBLISHER_ID,
                gemini_api_key=GEMINI_API_KEY,
                count=int(TOSS_PRODUCT_COUNT or 3),
            )
    except Exception as e:
        st.warning(f"토스 상품 삽입 실패 (글은 정상 생성됨): {e}")
        return blog_content

st.title("📝 AutoBlog 자동 포스팅 시스템")
st.markdown("네이버 뉴스 검색과 Gemini AI를 활용하여 팩트 기반의 블로그 글을 자동으로 생성합니다.")

# 우측 하단 Secrets에서 키를 관리하므로 API 키 상태만 조그맣게 표시
if not NAVER_API_KEY_ID or not GEMINI_API_KEY:
    st.warning("⚠️ 우측 하단의 [Manage app] -> [Settings] -> [Secrets] 메뉴에 API 키를 등록해야 정상 작동합니다.")

st.divider()

# 화면을 좌우 2분할 (왼쪽: 제어부, 오른쪽: 보관함)
col_left, col_right = st.columns([1, 1], gap="large")

TOPICS = [
    ("🏠 부동산", "부동산 핫이슈"),
    ("📈 경제/증권", "경제 증권 핫이슈"),
    ("⚖️ 정치", "정치 핫이슈"),
    ("👥 사회", "사회 핫이슈"),
    ("🧬 과학/IT", "과학 IT 핫이슈"),
    ("🌍 세계/국제", "국제 핫이슈"),
    ("🎤 연예", "연예계 핫이슈"),
    ("⚽ 스포츠", "스포츠 핫이슈")
]

with col_left:
    st.subheader("🚀 블로그 글 생성기")
    
    # --- 1. 일괄 생성 버튼 ---
    st.markdown("### ⚡ 8개 카테고리 자동 일괄 생성")
    st.write("버튼 한 번으로 8개 주제의 최신 뉴스를 모두 긁어와서 글 8개를 연속으로 완성합니다. (약 2~3분 소요)")
    if st.button("🚀 8개 전체 일괄 생성 시작 (커피 한 잔 마시고 오세요!)", type="primary", use_container_width=True):
        if not NAVER_API_KEY_ID or not GEMINI_API_KEY:
            st.error("API 키가 설정되지 않았습니다. 우측 하단 Secrets 설정을 확인해주세요!")
        else:
            with st.status("로봇이 8개의 글을 순차적으로 작성하고 있습니다...", expanded=True) as status:
                for icon, topic in TOPICS:
                    st.write(f"🔄 '{icon} {topic}' 작업 중...")
                    
                    news_items = fetch_latest_news(topic, display=5)
                    if not news_items: 
                        st.write(f"⚠️ '{topic}' 뉴스 검색 실패. 건너뜁니다.")
                        continue
                        
                    news_items_with_content = extract_contents_from_news_items(news_items)
                    if not news_items_with_content: 
                        st.write(f"⚠️ '{topic}' 본문 추출 실패. 건너뜁니다.")
                        continue
                        
                    blog_post_content = synthesize_blog_post(news_items_with_content, topic)

                    if not blog_post_content:
                        st.write(f"⚠️ '{topic}' 글 생성 실패: {getattr(synthesize_blog_post, 'last_error', '')}".strip()[:500])
                        continue
                    
                    if blog_post_content:
                        blog_post_content = _attach_toss_footer(blog_post_content, topic)
                        now = datetime.datetime.now()
                        ampm = "오전" if now.hour < 12 else "오후"
                        time_str = now.strftime(f"%Y-%m-%d {ampm} %I:%M")
                        
                        # 히스토리 리스트 맨 앞에 추가 (최신글이 위로 오게)
                        st.session_state.history.insert(0, {
                            "time": time_str,
                            "topic": topic,
                            "content": blog_post_content
                        })
                        st.write(f"✅ '{topic}' 완료!")
                        
                status.update(label="🎉 8개 카테고리 일괄 생성 완료!", state="complete", expanded=False)
                if not TOSS_ENABLED:
                    st.write("ℹ️ 토스쇼핑 키 미등록으로 상품 박스는 생략됐습니다. Secrets 등록 시 다음 글부터 자동 삽입됩니다.")
            st.success("작업 완료! 우측 [보관함]을 확인해주세요!")

    st.divider()
    
    # --- 2. 개별 생성 영역 ---
    st.markdown("### 🔍 개별 생성 (원하는 주제만)")
    keyword_input = st.text_input("키워드 입력 (예: 삼성전자 애플)", value=SEARCH_KEYWORD)
    
    # 버튼들
    cols1 = st.columns(4)
    cols2 = st.columns(4)
    selected_topic_for_single = None
    
    for i, (icon, topic) in enumerate(TOPICS):
        target_col = cols1[i] if i < 4 else cols2[i-4]
        if target_col.button(icon, use_container_width=True):
            selected_topic_for_single = topic
            
    target_keyword = selected_topic_for_single if selected_topic_for_single else keyword_input
    
    if st.button(f"▶️ '{target_keyword}'(으)로 개별 생성", use_container_width=True):
        if not NAVER_API_KEY_ID or not GEMINI_API_KEY:
            st.error("API 키가 설정되지 않았습니다. 우측 하단 Secrets 설정을 확인해주세요!")
        else:
            with st.status(f"'{target_keyword}' 작성 중...", expanded=True) as status:
                blog_post_content = None
                news_items = fetch_latest_news(target_keyword, display=5)
                if not news_items:
                    st.error("뉴스 검색 실패. 키 상태나 할당량을 확인해주세요.")
                else:
                    news_items_with_content = extract_contents_from_news_items(news_items)
                    if not news_items_with_content:
                        st.error("기사 본문 추출 실패.")
                    else:
                        blog_post_content = synthesize_blog_post(news_items_with_content, target_keyword)
                        if not blog_post_content:
                            st.error(f"블로그 글 생성 실패: {getattr(synthesize_blog_post, 'last_error', '')}".strip()[:500])
                
                if blog_post_content:
                    blog_post_content = _attach_toss_footer(blog_post_content, target_keyword)
                    now = datetime.datetime.now()
                    ampm = "오전" if now.hour < 12 else "오후"
                    time_str = now.strftime(f"%Y-%m-%d {ampm} %I:%M")
                    st.session_state.history.insert(0, {
                        "time": time_str,
                        "topic": target_keyword,
                        "content": blog_post_content
                    })
                    status.update(label="생성 완료!", state="complete", expanded=False)
                    if not TOSS_ENABLED:
                        st.caption("ℹ️ 토스쇼핑 키 미등록으로 상품 박스는 생략됐습니다.")


# --- 우측: 보관함 영역 ---
import streamlit.components.v1 as components

with col_right:
    st.subheader("🗂️ 완성된 블로그 글 보관함")
    st.write("방금 생성된 글들이 최신순으로 여기에 쌓입니다. 원하시는 글을 펼쳐서 복사하세요!")
    
    if not st.session_state.history:
        st.info("아직 생성된 글이 없습니다. 왼쪽에서 글을 생성해보세요!")
    else:
        for idx, item in enumerate(st.session_state.history):
            # 펼침막(Expander) UI 생성
            with st.expander(f"[{item['time']}] {item['topic']} 요약", expanded=(idx==0)):
                
                # 복사 버튼 (개별 ID 부여)
                safe_text = json.dumps(item['content'])
                copy_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
                </head>
                <body style="margin: 0; padding: 0;">
                    <button id="copyBtn_{idx}" style="width: 100%; padding: 10px; background-color: #ff4b4b; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 14px;">
                        📋 이 글 복사하기 (서식 포함)
                    </button>
                    
                    <script>
                        const mdText = {safe_text};
                        // 전체 글을 가운데 정렬하기 위해 div 태그로 감싸줌
                        const htmlText = "<div style='text-align: center;'>" + marked.parse(mdText) + "</div>";
                        
                        document.getElementById('copyBtn_{idx}').addEventListener('click', () => {{
                            const listener = (e) => {{
                                e.clipboardData.setData('text/html', htmlText);
                                e.clipboardData.setData('text/plain', mdText);
                                e.preventDefault();
                            }};
                            
                            document.addEventListener('copy', listener);
                            document.execCommand('copy');
                            document.removeEventListener('copy', listener);
                            
                            const btn = document.getElementById('copyBtn_{idx}');
                            btn.innerText = '✅ 복사 완료!';
                            btn.style.backgroundColor = '#28a745';
                            
                            setTimeout(() => {{
                                btn.innerText = '📋 이 글 복사하기 (서식 포함)';
                                btn.style.backgroundColor = '#ff4b4b';
                            }}, 3000);
                        }});
                    </script>
                </body>
                </html>
                """
                components.html(copy_html, height=50)
                
                # 내용 미리보기 (HTML 박스가 그대로 그려지도록)
                st.markdown(item['content'], unsafe_allow_html=True)
