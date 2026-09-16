from google import genai
from config import GEMINI_API_KEY
import re

def synthesize_blog_post(news_items, keyword):
    """
    여러 뉴스 본문을 종합하여 하나의 블로그 포스트(Markdown 포맷)로 작성합니다.
    """
    if not GEMINI_API_KEY:
        raise ValueError("Gemini API 키가 설정되지 않았습니다.")
        
    # 새로운 최신 Google GenAI 클라이언트 초기화
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # 프롬프트에 넣을 소스 텍스트 준비
    source_texts = ""
    for i, item in enumerate(news_items):
        title = re.sub(r'<[^>]+>', '', item['title']) # HTML 태그 제거
        source_texts += f"[기사 {i+1}] 제목: {title}\n내용: {item['content'][:1000]}...\n\n"
        
    prompt = f"""
당신은 IT/경제 분야의 전문 블로거입니다. 
아래 제공된 여러 건의 '{keyword}' 관련 최신 뉴스 기사들을 종합하여 
독자들이 읽기 쉽고 흥미로운 하나의 블로그 포스트를 작성해 주세요.

[요구사항]
1. 팩트 기반으로 내용을 종합할 것.
2. 서론, 본론(주요 이슈 요약), 결론(전망 및 인사이트)의 구조를 갖출 것.
3. 소제목을 사용하여 문단을 나눌 것.
4. 블로그 독자가 친근하게 느낄 수 있는 경어체(해요체/하십시오체)를 사용할 것.
5. 출처나 뉴스 링크를 명시적으로 적을 필요는 없음 (자연스럽게 녹여낼 것).
6. HTML이 아닌 Markdown 형식으로 작성할 것 (제목은 #, 소제목은 ## 등 활용).

[뉴스 기사 소스]
{source_texts}
"""
    
    try:
        # 2026년 최신 모델인 gemini-3.6-flash 사용
        response = client.models.generate_content(
            model='gemini-3.6-flash', 
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"[Synthesizer] 블로그 글 생성 중 오류 발생: {e}")
        return None
