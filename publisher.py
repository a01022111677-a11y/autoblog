import os
import datetime

def publish_to_naver_blog(title, content_md):
    """
    현재는 반자동(1번) 방식을 위해, 생성된 블로그 글을 파일(.md)로 저장합니다.
    추후 이 함수를 Selenium 기반의 완전 자동화 로직으로 교체할 수 있습니다.
    """
    print("==================================================")
    print(f"[{datetime.datetime.now()}] 블로그 포스트 생성 완료")
    print(f"제목: {title}")
    print("--------------------------------------------------")
    print(content_md)
    print("==================================================")
    
    # outputs 폴더 생성
    os.makedirs("outputs", exist_ok=True)
    
    # 파일명 설정 (예: 20260916_153022_경제.md)
    safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    filename = f"outputs/{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_title[:10]}.md"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")
            f.write(content_md)
        print(f"[Publisher] 글이 성공적으로 파일로 저장되었습니다. ➔ {filename}")
        print("[Publisher] 위 파일을 열어 내용을 확인하신 후 네이버 블로그에 복사/붙여넣기 하시면 됩니다!")
        return True
    except Exception as e:
        print(f"[Publisher] 파일 저장 중 오류 발생: {e}")
        return False
