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
    
    # 프롬프트에 넣을 소스 텍스트 및 여러 장의 이미지 준비
    source_texts = ""
    image_urls = []
    
    for i, item in enumerate(news_items):
        title = re.sub(r'<[^>]+>', '', item['title']) # HTML 태그 제거
        source_texts += f"[기사 {i+1}] 제목: {title}\n내용: {item['content'][:1000]}...\n\n"
        
        # 기사에 이미지가 있고, 중복되지 않으면 리스트에 추가
        if item.get('image_url') and item['image_url'] not in image_urls:
            image_urls.append(item['image_url'])
            
    # AI가 사용할 수 있도록 마크다운 이미지 태그 목록 생성
    images_instruction = ""
    if image_urls:
        images_instruction = "아래는 이번 뉴스들과 관련된 이미지 URL들입니다. 이 이미지들을 글 서론, 본문 사이사이, 결론 등에 적절하게 분산해서 모두 삽입해주세요. (반드시 마크다운 이미지 양식 `![사진설명](URL)`을 사용하세요!)\n"
        for url in image_urls:
            images_instruction += f"- {url}\n"
        
    prompt = f"""
당신은 '3분 카레'라는 닉네임을 쓰는 친근하고 활발한 네이버 블로그 운영자입니다. 
아래 제공된 여러 건의 '{keyword}' 관련 최신 뉴스 기사들을 종합하여 
독자들이 읽기 쉽고 흥미로운 하나의 블로그 포스트를 작성해 주세요.

반드시 아래의 양식과 어투를 엄격하게 지켜주세요.

[블로그 포스팅 양식 및 조건]
1. 제목 형태: `[{keyword} 요약] 👈 (어그로를 끄는 흥미로운 문구) ✨`
2. 도입부 인사말: "안녕하세요~ 이웃님들! 맛있는 정보와 핫한 소식을 물어다 주는 카레입니다~ 🍛👋" 로 반드시 시작하고, 계절이나 날씨, 최근 트렌드에 맞는 가벼운 수다로 글을 엽니다. 이모지를 아주 적극적으로 사용하세요.
3. 시각적 자료(사진) 적극 활용: 
{images_instruction}
4. 핵심 요약 박스: 글 서두(첫 번째 이미지 밑쯤)에 가장 중요한 내용을 3줄로 요약하는 박스를 만듭니다. (마크다운 인용구 `>` 활용)
   예시:
   > 📌 **{keyword} 핵심 3줄 요약**
   > ♦ (첫 번째 핵심 내용)
   > ♦ (두 번째 핵심 내용)
   > ♦ (세 번째 핵심 내용)
5. 본문 내용 (가독성 극대화): 스마트폰으로 읽는 사람들을 위해 **문장을 짧게 끊어 쓰고, 두세 줄마다 반드시 엔터(줄바꿈)를 여러 번 쳐서 여백을 넉넉하게** 주세요. 소제목(##)을 활용하여 내용이 빽빽해 보이지 않게 하고 중간중간 제공된 이미지를 넣어 시선을 분산시켜주세요. 말투는 전문가처럼 딱딱하게 쓰지 말고 이웃에게 이야기하듯 아주 친근하고 호들갑스러운 '해요체'를 사용하세요.
6. 마무리 인사: 카레만의 친근한 마무리 인사와 함께 댓글/공감을 유도하세요.

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
