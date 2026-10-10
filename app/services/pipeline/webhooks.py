"""webhook 投递

- 至少送达一次：投递记录先入库，由后台线程发送；失败按 10s → 30s → 2m → 10m → 30m → 1h → 3h 退避重试，
  接收方应按 event_id 去重；返回 410 表示对方不再需要，停止重试；
- 签名：X-Myolo-Signature: t=<unix秒>,v1=hex(HMAC_SHA256(secret, "<t>.<原始请求体>"))，
  接收方应校验签名并拒绝与当前时间相差超过 5 分钟的请求（防重放）；
- 防 SSRF：默认不允许回调内网/本机地址（WEBHOOK_ALLOWED_HOSTS 放行）。创建任务时检查一次，
  发送前按当时的 DNS 解析结果再检查一次（防 DNS 重绑定）。
"""
import hashlib
import hmac
import ipaddress
import json
import logging
import socket
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlsplit

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.api_key import ApiKey
from app.models.pipeline import PipelineRun, WebhookDelivery
from app.services.api_key_service import decrypt_secret, default_webhook_secret

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = [10, 30, 120, 600, 1800, 3600, 10800]
BATCH = 20


class WebhookTargetError(ValueError):
    """回调地址不允许（内网地址未放行、无法解析等）"""


def check_target(url: str) -> None:
    parts = urlsplit(url)
    host = parts.hostname
    if parts.scheme not in ("http", "https") or not host:
        raise WebhookTargetError("callback_url 必须是 http(s) 地址")
    allowed = {h.lower() for h in settings.WEBHOOK_ALLOWED_HOSTS}
    if "*" in allowed or host.lower() in allowed:
        return
    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise WebhookTargetError(f"callback_url 的主机名 {host} 无法解析")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if str(ip) in allowed:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise WebhookTargetError(
                f"callback_url 指向内网/本机地址 {ip}，默认不允许。如确需回调内网系统，请在 WEBHOOK_ALLOWED_HOSTS 中放行 {host}")


def sign(secret: str, body: bytes, timestamp: Optional[int] = None) -> str:
    t = int(timestamp if timestamp is not None else time.time())
    mac = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={t},v1={mac}"


def _secret_for(db, run: PipelineRun) -> str:
    if run.api_key_id:
        key = db.query(ApiKey).filter(ApiKey.id == run.api_key_id).first()
        secret = decrypt_secret(key.webhook_secret_enc) if key else None
        if secret:
            return secret
    return default_webhook_secret()


def deliver_once(db, delivery: WebhookDelivery) -> None:
    import httpx

    run = db.query(PipelineRun).filter(PipelineRun.id == delivery.run_id).first()
    body = json.dumps(delivery.payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    delivery.attempts += 1
    try:
        check_target(delivery.url)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Myolotrain-Webhook/1",
            "X-Myolo-Event": delivery.event_type,
            "X-Myolo-Delivery": str(delivery.payload.get("delivery_id", delivery.id)),
            "X-Myolo-Signature": sign(_secret_for(db, run), body) if run else "",
        }
        resp = httpx.post(delivery.url, content=body, headers=headers, timeout=settings.WEBHOOK_TIMEOUT_SECONDS,
                          follow_redirects=False)
        delivery.last_status_code = resp.status_code
        if 200 <= resp.status_code < 300:
            delivery.status, delivery.delivered_at, delivery.last_error = "delivered", datetime.utcnow(), None
            return
        if resp.status_code == 410:
            delivery.status, delivery.last_error = "failed", "接收方返回 410，停止重试"
            return
        delivery.last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except WebhookTargetError as e:
        delivery.status, delivery.last_error = "failed", str(e)   # 地址本身不允许，重试没有意义
        return
    except Exception as e:
        delivery.last_error = f"{type(e).__name__}: {e}"
    if delivery.attempts > len(BACKOFF_SECONDS):
        delivery.status = "failed"
    else:
        delivery.next_attempt_at = datetime.utcnow() + timedelta(seconds=BACKOFF_SECONDS[delivery.attempts - 1])


def deliver_due() -> int:
    db = SessionLocal()
    try:
        due = (db.query(WebhookDelivery)
               .filter(WebhookDelivery.status == "pending", WebhookDelivery.next_attempt_at <= datetime.utcnow())
               .order_by(WebhookDelivery.next_attempt_at).with_for_update(skip_locked=True).limit(BATCH).all())
        for d in due:
            deliver_once(db, d)
            db.commit()
        return len(due)
    finally:
        db.close()


class WebhookSender:
    def __init__(self):
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="webhook-sender", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                sent = deliver_due()
            except Exception:
                logger.exception("投递 webhook 出错")
                sent = 0
            self._stop.wait(0.5 if sent else 3)


webhook_sender = WebhookSender()
