"""飞书群聊消息抓取器 v2

增强功能：
- 获取用户真实名称（而非 open_id）
- 下载图片资源
- 富文本解析

使用方式:
    python3 chat_logger_v2.py --output ./chat_logs
"""

import argparse
import json
import os
import sys
from datetime import datetime

import requests

from config import Config
from feishu_api import FeishuAPI


def format_timestamp(ms: str) -> str:
    """将毫秒时间戳格式化为可读时间"""
    try:
        ts = int(ms) / 1000
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return ms


class UserCache:
    """用户名称缓存，避免重复查询"""

    def __init__(self, api: FeishuAPI):
        self.api = api
        self._cache = {}  # open_id -> name

    def get_name(self, user_id: str, id_type: str = "open_id") -> str:
        """获取用户真实名称"""
        if not user_id:
            return "未知"

        if user_id in self._cache:
            return self._cache[user_id]

        # 机器人
        if id_type == "app_id":
            name = "机器人"
            self._cache[user_id] = name
            return name

        # 查询用户信息
        try:
            url = f"{self.api.BASE_URL}/contact/v3/users/{user_id}"
            resp = requests.get(url, headers=self.api._headers(), timeout=30)
            result = resp.json()
            if result.get("code") == 0:
                user = result.get("data", {}).get("user", {})
                name = user.get("name", "") or user.get("en_name", "") or user.get("nickname", "")
                if name:
                    self._cache[user_id] = name
                    return name
        except Exception as e:
            print(f"   获取用户信息失败 {user_id}: {e}")

        # 降级：返回截断的ID
        self._cache[user_id] = user_id[:8]
        return self._cache[user_id]


def download_image(api: FeishuAPI, message_id: str, image_key: str,
                   output_dir: str) -> str:
    """下载图片资源"""
    url = f"{api.BASE_URL}/im/v1/messages/{message_id}/resources/{image_key}"
    params = {"type": "image"}

    try:
        resp = requests.get(url, headers=api._headers(), params=params,
                           timeout=60, stream=True)
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            ext = ".jpg"
            if "png" in content_type:
                ext = ".png"
            elif "gif" in content_type:
                ext = ".gif"
            elif "webp" in content_type:
                ext = ".webp"

            os.makedirs(output_dir, exist_ok=True)
            filename = f"{image_key[:16]}{ext}"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            return filepath
        else:
            try:
                err = resp.json()
                print(f"   图片下载失败: {err.get('msg', '')[:80]}")
            except Exception:
                print(f"   图片下载失败: HTTP {resp.status_code}")
    except Exception as e:
        print(f"   图片下载异常: {e}")

    return ""


def extract_message_content(msg: dict, api: FeishuAPI, user_cache: UserCache,
                            image_dir: str) -> dict:
    """从消息中提取完整内容"""
    msg_type = msg.get("msg_type", "")
    message_id = msg.get("message_id", "")
    result = {"text": "", "images": [], "raw_type": msg_type}

    if msg_type == "text":
        try:
            content = json.loads(msg.get("body", {}).get("content", "{}"))
            result["text"] = content.get("text", "")
        except Exception:
            result["text"] = "[文本解析失败]"

    elif msg_type == "post":
        try:
            content = json.loads(msg.get("body", {}).get("content", "{}"))
            texts = []
            zh_cn = content.get("zh_cn", {})
            for line in zh_cn.get("content", []):
                for item in line:
                    tag = item.get("tag", "")
                    if tag == "text":
                        texts.append(item.get("text", ""))
                    elif tag == "a":
                        texts.append(f"[{item.get('text', '链接')}]({item.get('href', '')})")
                    elif tag == "at":
                        user_id = item.get("user_id", "")
                        name = user_cache.get_name(user_id) if user_id else "某人"
                        texts.append(f"@{name}")
                    elif tag == "img":
                        image_key = item.get("image_key", "")
                        if image_key:
                            texts.append(f"[图片:{image_key[:16]}...]")
            result["text"] = " ".join(texts) or "[富文本消息]"
        except Exception:
            result["text"] = "[富文本解析失败]"

    elif msg_type == "image":
        try:
            content = json.loads(msg.get("body", {}).get("content", "{}"))
            image_key = content.get("image_key", "")
            if image_key and image_dir:
                filepath = download_image(api, message_id, image_key, image_dir)
                if filepath:
                    result["images"].append(filepath)
                    result["text"] = f"[图片:{os.path.basename(filepath)}]"
                else:
                    result["text"] = f"[图片:{image_key[:16]}... 下载失败]"
            else:
                result["text"] = f"[图片:{image_key[:16]}...]"
        except Exception:
            result["text"] = "[图片消息]"

    elif msg_type == "file":
        try:
            content = json.loads(msg.get("body", {}).get("content", "{}"))
            result["text"] = f"[文件] {content.get('file_name', '未知文件')}"
        except Exception:
            result["text"] = "[文件消息]"

    elif msg_type == "system":
        try:
            content = json.loads(msg.get("body", {}).get("content", "{}"))
            template = content.get("template", "")
            for key, val in content.items():
                if key != "template" and isinstance(val, list):
                    val_str = ", ".join(str(v) for v in val)
                    template = template.replace(f"{{{key}}}", val_str)
            result["text"] = f"[系统] {template}"
        except Exception:
            result["text"] = "[系统消息]"

    else:
        result["text"] = f"[{msg_type}消息]"

    return result


def fetch_chat_messages(api: FeishuAPI, chat_id: str, user_cache: UserCache,
                        image_dir: str = "", hours: int = None) -> list:
    """抓取群聊所有消息（自动分页）"""
    from datetime import timezone

    cutoff_ms = None
    if hours:
        cutoff_ms = int((datetime.now(timezone.utc).timestamp() - hours * 3600) * 1000)

    all_messages = []
    page_token = ""

    while True:
        result = api.get_chat_messages(chat_id, page_size=50, page_token=page_token)

        if result.get("code") != 0:
            print(f"获取群消息失败: {result.get('msg', '')}")
            break

        data = result.get("data", {})
        items = data.get("items", [])

        for msg in items:
            create_time = int(msg.get("create_time", "0"))

            if cutoff_ms and create_time < cutoff_ms:
                continue

            sender = msg.get("sender", {})
            sender_type = sender.get("sender_type", "unknown")
            sender_id = sender.get("id", "")
            sender_id_type = sender.get("id_type", "")

            # 获取发送者名称
            if sender_type == "app":
                sender_name = "机器人"
            elif sender_type == "user":
                sender_name = user_cache.get_name(sender_id, sender_id_type)
            else:
                sender_name = sender_type

            # 提取消息内容
            content = extract_message_content(msg, api, user_cache, image_dir)

            all_messages.append({
                "time": format_timestamp(msg.get("create_time", "")),
                "timestamp": create_time,
                "sender_name": sender_name,
                "sender_type": sender_type,
                "sender_id": sender_id,
                "msg_type": msg.get("msg_type", ""),
                "message_id": msg.get("message_id", ""),
                "text": content["text"],
                "images": content["images"],
            })

        page_token = data.get("page_token", "")
        has_more = data.get("has_more", False)

        if not has_more or not page_token:
            break

    # 按时间排序（新的在前）
    all_messages.sort(key=lambda x: x["timestamp"], reverse=True)
    return all_messages


def save_to_file(messages: list, chat_id: str, output_dir: str,
                 chat_name: str = "", image_dir: str = "") -> str:
    """将消息保存到文本文件"""
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d")
    safe_name = (chat_name or chat_id).replace("/", "_").replace("\\", "_")
    filename = f"{timestamp}_{safe_name}.txt"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"群聊消息记录\n")
        f.write(f"群名: {chat_name or chat_id}\n")
        f.write(f"群ID: {chat_id}\n")
        f.write(f"抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"消息总数: {len(messages)}\n")
        if image_dir:
            f.write(f"图片目录: {image_dir}\n")
        f.write("=" * 60 + "\n\n")

        for msg in messages:
            f.write(f"[{msg['time']}] ")
            f.write(f"{msg['sender_name']}: ")
            f.write(f"{msg['text']}\n")
            for img in msg.get("images", []):
                f.write(f"    [图片文件: {os.path.basename(img)}]\n")
            f.write("\n")

    return filepath


def save_to_json(messages: list, chat_id: str, output_dir: str,
                 chat_name: str = "") -> str:
    """将消息保存为JSON文件"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")
    safe_name = (chat_name or chat_id).replace("/", "_").replace("\\", "_")
    filename = f"{timestamp}_{safe_name}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "chat_id": chat_id,
            "chat_name": chat_name,
            "fetch_time": datetime.now().isoformat(),
            "message_count": len(messages),
            "messages": messages,
        }, f, indent=2, ensure_ascii=False)

    return filepath


def get_chat_name(api: FeishuAPI, chat_id: str) -> str:
    """获取群聊名称"""
    url = f"{api.BASE_URL}/im/v1/chats/{chat_id}"
    try:
        resp = requests.get(url, headers=api._headers(), timeout=30)
        result = resp.json()
        if result.get("code") == 0:
            return result.get("data", {}).get("name", chat_id)
    except Exception:
        pass
    return chat_id


def main() -> int:
    parser = argparse.ArgumentParser(description="飞书群聊消息抓取器")
    parser.add_argument("--chat-id", default="", help="指定群聊ID（多个用逗号分隔）")
    parser.add_argument("--hours", type=int, default=None, help="只抓取最近N小时的消息")
    parser.add_argument("--output", default="", help="输出目录")
    parser.add_argument("--download-images", action="store_true", help="下载图片资源")
    parser.add_argument("--image-dir", default="", help="图片保存目录")
    parser.add_argument("--format", default="txt", choices=["txt", "json"], help="输出格式")
    args = parser.parse_args()

    config = Config.from_env()

    if not config.app_id or not config.app_secret:
        print("配置错误: FEISHU_APP_ID, FEISHU_APP_SECRET 必须设置")
        return 1

    # 输出目录
    output_dir = args.output or config.save_dir

    # 确定要抓取的群列表
    if args.chat_id:
        chat_ids = [cid.strip() for cid in args.chat_id.split(",") if cid.strip()]
    else:
        chat_ids = config.get_chat_ids()

    if not chat_ids:
        print("没有配置群聊ID")
        return 1

    print("=" * 60)
    print("飞书群聊消息抓取器")
    print("=" * 60)
    print(f"   输出目录: {os.path.abspath(output_dir)}")
    print(f"   抓取群数: {len(chat_ids)}")
    if args.hours:
        print(f"   时间范围: 最近 {args.hours} 小时")
    else:
        print(f"   时间范围: 全部历史消息")
    print(f"   下载图片: {'是' if args.download_images else '否'}")
    print(f"   输出格式: {args.format}")
    print()

    api = FeishuAPI(config.app_id, config.app_secret)
    user_cache = UserCache(api)
    total_messages = 0
    saved_files = []

    for chat_id in chat_ids:
        print(f"\n正在抓取群: {chat_id}")

        chat_name = get_chat_name(api, chat_id)
        print(f"   群名: {chat_name}")

        # 图片目录
        image_dir = ""
        if args.download_images:
            image_dir = args.image_dir or os.path.join(output_dir, "images", chat_name)

        try:
            messages = fetch_chat_messages(api, chat_id, user_cache,
                                           image_dir=image_dir, hours=args.hours)
        except Exception as e:
            print(f"   抓取失败: {e}")
            continue

        if not messages:
            print("   该群没有消息")
            continue

        print(f"   获取到 {len(messages)} 条消息")

        if args.format == "json":
            filepath = save_to_json(messages, chat_id, output_dir, chat_name)
        else:
            filepath = save_to_file(messages, chat_id, output_dir, chat_name, image_dir)
        saved_files.append(filepath)
        total_messages += len(messages)
        print(f"   已保存: {filepath}")

    print("\n" + "=" * 60)
    print("抓取完成")
    print(f"   总消息数: {total_messages}")
    print(f"   保存文件: {len(saved_files)} 个")
    for f in saved_files:
        print(f"   - {f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
