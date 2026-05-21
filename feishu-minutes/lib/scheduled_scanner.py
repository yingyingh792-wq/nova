"""飞书群消息定时扫描器

定时扫描指定群聊的历史消息，查找妙记链接并自动处理。
"""

import json
import os
import re
import sys
from datetime import datetime

from config import Config
from feishu_api import FeishuAPI
from main import _process_single_url, extract_minute_token
from transcript_scraper import TranscriptScraper

# 已处理链接记录文件
PROCESSED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".processed_minutes.json")


def load_processed() -> set:
    """加载已处理的妙记token集合"""
    if not os.path.exists(PROCESSED_FILE):
        return set()
    try:
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("tokens", []))
    except Exception:
        return set()


def save_processed(tokens: set) -> None:
    """保存已处理的妙记token集合"""
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "tokens": list(tokens),
            "updated_at": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)


def extract_minutes_urls(text: str) -> list:
    """从文本中提取妙记URL"""
    patterns = [
        r'https?://[\w\-]+\.feishu\.cn/minutes/[a-zA-Z0-9]+',
        r'https?://[\w\-]+\.larksuite\.com/minutes/[a-zA-Z0-9]+',
    ]
    urls = []
    for pattern in patterns:
        urls.extend(re.findall(pattern, text))
    return list(set(urls))


def scan_chat_messages(api: FeishuAPI, chat_id: str, hours: int = 24) -> list:
    """扫描群聊消息，返回发现的妙记链接列表"""
    print(f"\n扫描群聊消息（最近 {hours} 小时）...")

    try:
        messages = api.get_chat_history(container_id=chat_id, hours=hours)
    except Exception as e:
        print(f"获取群消息失败: {e}")
        return []

    print(f"   共获取 {len(messages)} 条消息")

    found = []
    for msg in messages:
        msg_type = msg.get("msg_type", "")
        if msg_type != "text":
            continue

        try:
            content = json.loads(msg.get("body", {}).get("content", "{}"))
            text = content.get("text", "")
        except (json.JSONDecodeError, KeyError):
            continue

        urls = extract_minutes_urls(text)
        if urls:
            sender = msg.get("sender", {}).get("sender_id", {}).get("open_id", "未知")
            create_time = msg.get("create_time", "")
            for url in urls:
                found.append((url, sender, create_time))
                print(f"   发现妙记链接: {url}")

    return found


def process_new_minutes(urls: list, processed: set, api: FeishuAPI,
                        scraper: TranscriptScraper, config: Config,
                        notify: bool = False) -> dict:
    """处理新发现的妙记链接"""
    results = {
        "total": len(urls),
        "new": 0,
        "skipped": 0,
        "success": 0,
        "failed": 0,
        "details": []
    }

    for url, sender, send_time in urls:
        try:
            token = extract_minute_token(url)
        except ValueError:
            results["failed"] += 1
            continue

        if token in processed:
            print(f"   已处理过，跳过: {url}")
            results["skipped"] += 1
            continue

        results["new"] += 1
        print(f"\n{'─' * 50}")
        print(f"处理新妙记: {url}")

        success = _process_single_url(url, api, scraper, config)

        if success:
            processed.add(token)
            save_processed(processed)
            results["success"] += 1
            results["details"].append({"url": url, "status": "success"})
        else:
            results["failed"] += 1
            results["details"].append({"url": url, "status": "failed"})

    if notify and results["new"] > 0:
        send_summary_report(api, config.chat_id, results)

    return results


def send_summary_report(api: FeishuAPI, chat_id: str, results: dict) -> None:
    """发送扫描汇总报告到群聊"""
    if results["new"] == 0:
        return

    message = f"""妙记定时扫描报告

扫描结果:
   新发现: {results['new']} 条
   成功处理: {results['success']} 条
   处理失败: {results['failed']} 条
   已跳过（重复）: {results['skipped']} 条

扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""

    try:
        api.send_text_message(chat_id, message)
        print("\n汇总报告已发送到群聊")
    except Exception as e:
        print(f"\n发送报告失败: {e}")
