"""配置管理"""

import os
from dataclasses import dataclass


def _load_dotenv(path: str = None) -> None:
    """手动加载 .env 文件到环境变量"""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


@dataclass
class Config:
    """应用配置"""

    app_id: str
    app_secret: str
    chat_id: str
    save_dir: str = "./meeting_transcripts"
    headless: bool = True
    cookie_file: str = "./cookies/lark_cookies.json"

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量和 .env 文件读取配置"""
        _load_dotenv()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return cls(
            app_id=os.getenv("FEISHU_APP_ID", ""),
            app_secret=os.getenv("FEISHU_APP_SECRET", ""),
            chat_id=os.getenv("FEISHU_CHAT_ID", ""),
            save_dir=os.getenv("SAVE_DIR", os.path.join(base_dir, "meeting_transcripts")),
            headless=os.getenv("HEADLESS", "true").lower() == "true",
            cookie_file=os.getenv("COOKIE_FILE", os.path.join(base_dir, "cookies", "lark_cookies.json")),
        )

    def get_chat_ids(self) -> list:
        """获取所有配置的群聊ID列表"""
        return [cid.strip() for cid in self.chat_id.split(",") if cid.strip()]
