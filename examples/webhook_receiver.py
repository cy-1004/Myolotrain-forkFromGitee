"""webhook 接收端示例：校验签名并打印事件

    python examples/webhook_receiver.py --port 8399 --secret whsec_xxx

服务端配置 WEBHOOK_ALLOWED_HOSTS='["127.0.0.1"]' 才能回调本机地址。
签名规则：X-Myolo-Signature: t=<unix秒>,v1=hex(HMAC_SHA256(secret, "<t>.<原始请求体>"))
"""
import argparse
import hashlib
import hmac
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

MAX_SKEW_SECONDS = 300


def verify(secret: str, header: str, body: bytes) -> bool:
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        t, sig = int(parts["t"]), parts["v1"]
    except (KeyError, ValueError):
        return False
    if abs(time.time() - t) > MAX_SKEW_SECONDS:   # 防重放
        return False
    expected = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8399)
    p.add_argument("--secret", required=True)
    p.add_argument("--log", help="把收到的事件追加写入该文件（每行一个 JSON）")
    a = p.parse_args()
    seen = set()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            ok = verify(a.secret, self.headers.get("X-Myolo-Signature", ""), body)
            if not ok:
                self.send_response(401)
                self.end_headers()
                print("签名校验失败，已拒绝")
                return
            event = json.loads(body)
            duplicate = event["event_id"] in seen   # 至少送达一次：按 event_id 去重
            seen.add(event["event_id"])
            print(f"{'(重复) ' if duplicate else ''}{event['event']} job={event['job']['job_id']} status={event['job']['status']}")
            if a.log:
                with open(a.log, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"verified": True, "duplicate": duplicate, **event}, ensure_ascii=False) + "\n")
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    print(f"监听 http://127.0.0.1:{a.port}/")
    HTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
