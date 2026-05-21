"""飞书 Open API 客户端"""

import json
import time
from typing import Optional

import requests


class FeishuAPI:
    """飞书 API 封装"""

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
