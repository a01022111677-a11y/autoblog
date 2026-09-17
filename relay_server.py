"""토스쇼핑 OpenAPI 중계 서버 (집PC / 고정IP 서버용).

왜 필요한가:
  토스 OpenAPI는 어드민에 등록된 고정 IP에서만 호출을 허용한다.
  Streamlit Cloud는 출발지 IP가 유동이라 직접 호출하면
  SHARELINK_OPENAPI_ACCESS_DENIED로 차단된다.
  이 서버를 고정IP 머신에서 띄우고 그 IP를 토스 어드민에 등록하면,
  Cloud 앱이 이 중계기를 거쳐 전자동 발급을 쓸 수 있다.

실행 (집PC, 키는 .env 또는 환경변수에):
  set RELAY_SECRET=아주긴랜덤문자열   (PowerShell)
  python relay_server.py --port 8000

외부 공개 (포트포워딩 없이, Cloudflare Tunnel 무료):
  cloudflared tunnel --url http://localhost:8000
  → 발급된 https URL을 Cloud Secrets의 TOSS_RELAY_URL에 등록

필요 Secrets (Cloud 쪽):
  TOSS_RELAY_URL = "https://xxx.trycloudflare.com"
  TOSS_RELAY_SECRET = "위 RELAY_SECRET과 동일한 값"

주의:
  - RELAY_SECRET은 추측 불가한 긴 랜덤 문자열로! (유출 시 중계기 남용 가능)
  - 집PC는 글 생성할 때만 켜져 있으면 된다.
"""
import json
import os
import sys
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.toss_shopping import (
    fetch_best_selling,
    fetch_today_deals,
    issue_sharelink,
)
from config import TOSS_ACCESS_KEY, TOSS_SECRET_KEY, TOSS_PUBLISHER_ID


class Handler(BaseHTTPRequestHandler):
    server_version = "TossRelay/1.0"

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self):
        # /health는 인증 없이, 나머지는 공유 비밀키 필수
        if urlparse(self.path).path == "/health":
            return True
        secret = os.getenv("RELAY_SECRET", "")
        if not secret:
            return False
        return self.headers.get("X-Relay-Secret", "") == secret

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except Exception:
            length = 0
        if length <= 0 or length > 65536:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            return {}

    def _need_keys(self):
        return bool(TOSS_ACCESS_KEY and TOSS_SECRET_KEY)

    def do_GET(self):
        if not self._authed():
            return self._send(401, {"ok": False, "error": "unauthorized"})
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        try:
            if parsed.path == "/health":
                return self._send(200, {"ok": True, "data": {"toss_keys": self._need_keys()}})
            if parsed.path == "/toss/best-selling":
                if not self._need_keys():
                    return self._send(200, {"ok": False, "error": "중계서버에 토스 키(.env) 없음"})
                size = int((qs.get("size") or ["30"])[0])
                items = fetch_best_selling(TOSS_ACCESS_KEY, TOSS_SECRET_KEY, size=size)
                return self._send(200, {"ok": True, "data": items})
            if parsed.path == "/toss/today-deals":
                if not self._need_keys():
                    return self._send(200, {"ok": False, "error": "중계서버에 토스 키(.env) 없음"})
                size = int((qs.get("size") or ["10"])[0])
                items = fetch_today_deals(TOSS_ACCESS_KEY, TOSS_SECRET_KEY, size=size)
                return self._send(200, {"ok": True, "data": items})
            return self._send(404, {"ok": False, "error": "not found"})
        except Exception as e:
            return self._send(200, {"ok": False, "error": str(e)[:500]})

    def do_POST(self):
        if not self._authed():
            return self._send(401, {"ok": False, "error": "unauthorized"})
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/toss/links":
                body = self._body()
                if not self._need_keys():
                    return self._send(200, {"ok": False, "error": "중계서버에 토스 키(.env) 없음"})
                if not TOSS_PUBLISHER_ID:
                    return self._send(200, {"ok": False, "error": "중계서버에 TOSS_PUBLISHER_ID 없음"})
                link = issue_sharelink(
                    TOSS_ACCESS_KEY, TOSS_SECRET_KEY,
                    TOSS_PUBLISHER_ID, body.get("tacaItemId"),
                )
                return self._send(200, {"ok": True, "data": link})
            return self._send(404, {"ok": False, "error": "not found"})
        except Exception as e:
            return self._send(200, {"ok": False, "error": str(e)[:500]})

    def log_message(self, fmt, *args):
        print(f"[Relay] {self.address_string()} {fmt % args}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.getenv("RELAY_PORT", "8000")))
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    if not os.getenv("RELAY_SECRET"):
        print("[Relay] 경고: RELAY_SECRET이 비어 있습니다. 반드시 긴 랜덤 문자열을 설정하세요!")
    print(f"[Relay] 토스키 등록 여부: {bool(TOSS_ACCESS_KEY and TOSS_SECRET_KEY)}")
    print(f"[Relay] 리슨 중: http://{args.host}:{args.port} (외부 공개는 cloudflared tunnel 사용)")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Relay] 종료")


if __name__ == "__main__":
    main()
