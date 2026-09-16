from newspaper import Article
import time

def extract_article_content(url):
    """
    주어진 뉴스 URL에서 본문 텍스트를 추출합니다.
    """
    try:
        # newspaper3k를 이용한 본문 추출
        article = Article(url, language='ko')
        article.download()
        article.parse()
        
        # 텍스트가 너무 짧으면 추출 실패로 간주
        if len(article.text) < 50:
            return None
            
        return article.text
    except Exception as e:
        print(f"[Content Extractor] 본문 추출 중 오류 발생 ({url}): {e}")
        return None

def extract_contents_from_news_items(news_items):
    """
    뉴스 아이템 리스트에서 본문을 모두 추출하여 딕셔너리에 담아 반환합니다.
    """
    results = []
    for item in news_items:
        # 네이버 기사의 경우 originallink를 우선적으로 시도, 안되면 link 사용
        url_to_parse = item.get("originallink") or item.get("link")
        
        print(f"[{item['title']}] 본문 추출 시도 중... ({url_to_parse})")
        content = extract_article_content(url_to_parse)
        
        if content:
            item['content'] = content
            results.append(item)
        
        # 크롤링 차단 방지를 위한 딜레이
        time.sleep(1)
        
    return results
