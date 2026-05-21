"""飞书 Open API 客户端"""

import json
import time
from typing import Optional

import requests


class FeishuAPI:
    """飞书 API 封装"""

    # 国内版飞书 API 域名（默认）
    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: Optional[str] = None
        self._token_expires_at: float = 0

    def _get_tenant_access_token(self) -> str:
        """获取 tenant_access_token，带缓存机制"""
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise Exception(f"获取 tenant_access_token 失败: {data}")

        self._token = data["tenant_access_token"]
        self._token_expires_at = time.time() + data.get("expire", 7200)
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_tenant_access_token()}",
            "Content-Type": "application/json; charset=utf-8"
        }

    def get_minutes_info(self, minute_token: str) -> dict:
        """获取妙记基本信息（标题、URL、时长等）"""
        url = f"{self.BASE_URL}/minutes/v1/minutes/{minute_token}"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_minutes_media(self, minute_token: str) -> dict:
        """获取妙记音视频临时下载链接（有效期1天）"""
        url = f"{self.BASE_URL}/minutes/v1/minutes/{minute_token}/media"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def send_text_message(self, receive_id: str, text: str, receive_id_type: str = "chat_id") -> dict:
        """发送文本消息到群聊或个人"""
        url = f"{self.BASE_URL}/im/v1/messages?receive_id_type={receive_id_type}"
        body = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False)
        }
        resp = requests.post(url, headers=self._headers(), json=body, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_chat_messages(self, container_id: str, page_size: int = 50,
                          page_token: str = "") -> dict:
        """获取群聊消息列表"""
        url = f"{self.BASE_URL}/im/v1/messages"
        params = {
            "container_id_type": "chat",
            "container_id": container_id,
            "page_size": min(page_size, 50),
        }
        if page_token:
            params["page_token"] = page_token

        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_chat_history(self, container_id: str, hours: int = 24) -> list:
        """批量获取群聊历史消息（自动分页，本地过滤时间）"""
        from datetime import datetime, timezone

        cutoff_ms = int((datetime.now(timezone.utc).timestamp() - hours * 3600) * 1000)

        all_messages = []
        page_token = ""

        while True:
            result = self.get_chat_messages(
                container_id=container_id,
                page_size=50,
                page_token=page_token,
            )

            if result.get("code") != 0:
                print(f"获取群消息失败: {result.get('msg')}")
                break

            data = result.get("data", {})
            items = data.get("items", [])

            for item in items:
                create_time = int(item.get("create_time", "0"))
                if create_time >= cutoff_ms:
                    all_messages.append(item)

            page_token = data.get("page_token", "")
            has_more = data.get("has_more", False)

            if not has_more or not page_token:
                break

        return all_messages
