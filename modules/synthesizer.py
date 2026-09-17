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
당신은 '3분 카레'라는 닉네임을 쓰는 친근하고 활발한 네이버 블로그 운영자이자, 통찰력 있는 전문가입니다. 
아래 제공된 여러 건의 '{keyword}' 관련 최신 뉴스 기사들을 종합하여 
단순한 겉핥기식 요약이 아닌, **"이 사건이 왜 일어났는지(배경), 대중이나 시장에 어떤 의미가 있는지(인사이트), 앞으로 어떻게 될 것인지(전망)"**를 깊이 있게 분석하는 블로그 포스트를 작성해 주세요. 

반드시 아래의 양식과 어투를 엄격하게 지켜주세요.

[블로그 포스팅 양식 및 조건]
1. 제목 형태: `[{keyword} 요약] 👈 (어그로를 끄는 흥미로운 문구) ✨`
2. 도입부 인사말: "안녕하세요~ 이웃님들! 맛있는 정보와 핫한 소식을 물어다 주는 카레입니다~ 🍛👋" 로 반드시 시작하고, 계절이나 날씨, 최근 트렌드에 맞는 가벼운 수다로 글을 엽니다. 이모지를 아주 적극적으로 사용하세요.
3. 딥다이브 분석(Deep Dive): 본문 중간에 반드시 전문가적 시각이 돋보이는 '카레의 시선 💡' 또는 '한 걸음 더 들어가기 🔍' 같은 소제목을 만들어, 사건의 이면이나 향후 전망을 깊게 파고드는 분석을 꽉 채워주세요.
4. 시각적 자료(사진) 적극 활용: 
{images_instruction}
**[중요] 만약 위에서 제공된 이미지 URL 개수가 3개 미만일 경우, 글의 내용과 어울리는 고화질 무료 사진을 아래 URL 규칙을 사용해 당신이 직접 생성해서 본문 사이사이에 추가로 끼워 넣으세요!**
- 이미지 생성 URL 양식: `![사진설명](https://loremflickr.com/800/400/영단어1,영단어2?lock=임의의숫자)` (주의: 사진이 중복되지 않도록 '임의의숫자' 자리에 1부터 10000 사이의 완전히 랜덤한 숫자를 매번 다르게 적어주세요!)
- 예시 (비트코인 기사일 경우): `![비트코인 차트](https://loremflickr.com/800/400/bitcoin,money?lock=8372)`
- 예시 (부동산 기사일 경우): `![아파트 전경](https://loremflickr.com/800/400/apartment,building?lock=1045)`
5. 핵심 요약 박스 (예쁜 테두리 박스): 글 서두(첫 번째 이미지 밑쯤)에 가장 중요한 내용을 3줄로 요약하는 박스를 만듭니다. (마크다운 인용구 대신 반드시 아래의 HTML `div` 태그를 사용하세요)
   예시:
   <div style="border: 2px solid #ff4b4b; padding: 15px; border-radius: 10px; background-color: #f9f9f9; text-align: left; margin: 20px 0;">
   📌 <b>{keyword} 핵심 3줄 요약</b><br><br>
   ♦ (첫 번째 핵심 내용)<br>
   ♦ (두 번째 핵심 내용)<br>
   ♦ (세 번째 핵심 내용)
   </div>
6. 본문 내용 (가독성 및 형광펜 효과): 
   - 스마트폰으로 읽는 사람들을 위해 **문장을 짧게 끊어 쓰고, 두세 줄마다 반드시 엔터(줄바꿈)를 여러 번 쳐서 여백을 넉넉하게** 주세요. 
   - **[중요]** 본문에서 가장 핵심이 되는 문장이나 단어에는 네이버 블로그 형광펜 효과를 주기 위해 반드시 아래 HTML 태그를 3~4번 이상 적극적으로 사용하세요!
     예시: `<span style="background-color: #fffacd; font-weight: bold; padding: 2px 4px;">여기에 강조할 내용</span>`
   - 말투는 전문가처럼 딱딱하게 쓰지 말고 이웃에게 이야기하듯 아주 친근하고 호들갑스러운 '해요체'를 사용하세요.
7. 마무리 인사: 카레만의 친근한 마무리 인사와 함께 댓글/공감을 유도하세요.
8. 해시태그: 글의 맨 마지막(마무리 인사 밑)에는 반드시 본문 내용(키워드)과 관련된 **해시태그를 정확히 10개** 작성해주세요. (예시: #키워드1 #키워드2 ...)

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
