#!/usr/bin/env python3
"""飞书妙记自动收集工具

功能：
    1. 获取妙记信息（标题、URL、时长）
    2. 发送妙记链接到指定飞书群聊
    3. 自动下载会议转写文字到本地

使用方法：
    # 处理单个妙记
    python3 main.py "https://minutes.feishu.cn/minutes/xxxxx"

    # 首次运行（需要登录飞书）
    python3 main.py "https://minutes.feishu.cn/minutes/xxxxx" --no-headless

    # 批量处理
    python3 main.py --file urls.txt

    # 扫描群消息中的妙记链接
    python3 main.py --scan --scan-hours 24
"""

import argparse
import os
import re
import sys

from config import Config
from feishu_api import FeishuAPI
from transcript_scraper import TranscriptScraper


def extract_minute_token(url: str) -> str:
    """从妙记 URL 中提取 minute_token"""
    patterns = [
        r"/minutes/([a-zA-Z0-9]+)",
        r"minutes\.feishu\.cn/minutes/([a-zA-Z0-9]+)",
        r"minutes\.larksuite\.com/minutes/([a-zA-Z0-9]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"无法从 URL 中提取 minute_token: {url}")


def format_duration(seconds: int) -> str:
    """格式化秒数为可读时长"""
    if not seconds:
        return "未知"
    minutes, secs = divmod(seconds, 60)
    hours, mins = divmod(minutes, 60)
    if hours:
        return f"{hours}小时{mins}分{secs}秒"
    return f"{mins}分{secs}秒"


def validate_config(config: Config) -> bool:
    """验证配置是否完整"""
    errors = []
    if not config.app_id:
        errors.append("FEISHU_APP_ID 未设置")
    if not config.app_secret:
        errors.append("FEISHU_APP_SECRET 未设置")
    if not config.chat_id:
        errors.append("FEISHU_CHAT_ID 未设置")

    if errors:
        print("配置错误：")
        for err in errors:
            print(f"   - {err}")
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="飞书妙记自动收集工具")
    parser.add_argument("url", nargs="?", default="", help="妙记 URL")
    parser.add_argument("--file", "-f", default="", help="URL列表文件")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口（首次登录需要）")
    parser.add_argument("--selector", default="", help="自定义CSS选择器")
    parser.add_argument("--scan", action="store_true", help="扫描群消息中的妙记链接")
    parser.add_argument("--scan-hours", type=int, default=24, help="扫描最近N小时的消息")
    parser.add_argument("--scan-notify", action="store_true", help="扫描完成后发送汇总报告")
    parser.add_argument("--output", "-o", default="", help="输出目录（覆盖默认）")
    args = parser.parse_args()

    # 扫描模式
    if args.scan:
        from scheduled_scanner import scan_chat_messages, load_processed, save_processed, process_new_minutes

        config = Config.from_env()
        config.headless = not args.no_headless
        if args.output:
            config.save_dir = args.output

        if not validate_config(config):
            return 1

        print("=" * 50)
        print("群消息扫描模式")
        print("=" * 50)
        print(f"   扫描范围: 最近 {args.scan_hours} 小时")

        processed = load_processed()
        print(f"   已处理记录: {len(processed)} 条")

        api = FeishuAPI(config.app_id, config.app_secret)
        scraper = TranscriptScraper(
            cookie_file=config.cookie_file,
            headless=config.headless
        )

        # 逐个群扫描
        chat_ids = config.get_chat_ids()
        print(f"   扫描群数: {len(chat_ids)}")

        all_found = []
        for i, chat_id in enumerate(chat_ids, 1):
            print(f"\n   [{i}/{len(chat_ids)}] 扫描群: {chat_id}")
            found = scan_chat_messages(api, chat_id, hours=args.scan_hours)
            if found:
                print(f"      发现 {len(found)} 个妙记链接")
                all_found.extend(found)
            else:
                print(f"      未发现妙记链接")

        if not all_found:
            print("\n所有群均未发现妙记链接")
            return 0

        print(f"\n共发现 {len(all_found)} 个妙记链接")
        results = process_new_minutes(
            all_found, processed, api, scraper, config,
            notify=args.scan_notify
        )

        print("\n" + "=" * 50)
        print(f"   新发现: {results['new']} 条")
        print(f"   成功: {results['success']} 条")
        print(f"   失败: {results['failed']} 条")
        print(f"   跳过: {results['skipped']} 条")
        return 0

    # 收集要处理的URL列表
    urls = []
    if args.file:
        if not os.path.exists(args.file):
            print(f"URL列表文件不存在: {args.file}")
            return 1
        with open(args.file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
        if not urls:
            print(f"URL列表文件为空: {args.file}")
            return 1
    elif args.url:
        urls = [args.url]
    else:
        print("请提供妙记 URL 或使用 --file 指定URL列表文件")
        print("   python3 main.py 'https://minutes.feishu.cn/minutes/xxxxx'")
        print("   python3 main.py --file urls.txt")
        print("   python3 main.py --scan --scan-hours 24")
        return 1

    # 读取配置
    config = Config.from_env()
    config.headless = not args.no_headless
    if args.output:
        config.save_dir = args.output

    if not validate_config(config):
        return 1

    print("=" * 50)
    print("飞书妙记自动收集工具")
    print("=" * 50)
    print(f"   待处理URL数: {len(urls)}")
    print(f"   保存目录: {os.path.abspath(config.save_dir)}")
    print(f"   浏览器模式: {'headless' if config.headless else '可视化'}")
    print()

    api = FeishuAPI(config.app_id, config.app_secret)
    scraper = TranscriptScraper(
        cookie_file=config.cookie_file,
        headless=config.headless
    )

    success_count = 0
    fail_count = 0

    for idx, url in enumerate(urls, 1):
        print(f"\n{'─' * 50}")
        print(f"[{idx}/{len(urls)}] 处理: {url}")
        print("─" * 50)

        result = _process_single_url(url, api, scraper, config, debug=args.debug, custom_selector=args.selector)
        if result:
            success_count += 1
        else:
            fail_count += 1

    print("\n" + "=" * 50)
    print(f"处理完成！成功 {success_count} / 失败 {fail_count}")
    print("=" * 50)
    return 0 if fail_count == 0 else 1


def _process_single_url(url: str, api: FeishuAPI, scraper: TranscriptScraper,
                        config: Config, debug: bool = False,
                        custom_selector: str = "") -> bool:
    """处理单个妙记URL，返回是否成功"""

    # 提取 minute_token
    try:
        minute_token = extract_minute_token(url)
        print(f"   提取 minute_token: {minute_token}")
    except ValueError as e:
        print(f"   {e}")
        return False

    # 获取妙记信息
    print("\n   步骤 1/3: 获取妙记信息...")
    title = "未命名会议"
    minutes_url = url
    duration = 0

    try:
        info = api.get_minutes_info(minute_token)
        if info.get("code") == 0:
            data = info["data"]
            title = data.get("title", title)
            minutes_url = data.get("url", url)
            duration = data.get("duration", 0)
            print(f"   标题: {title}")
            print(f"   时长: {format_duration(duration)}")
        else:
            print(f"   获取妙记信息失败: {info.get('msg')}，使用默认信息继续")
    except Exception as e:
        print(f"   API 请求失败: {e}，使用默认信息继续")

    # 发送消息到群聊
    print(f"\n   步骤 2/3: 发送消息到群聊...")

    message = f"""会议妙记已生成

标题：{title}
时长：{format_duration(duration)}
链接：{minutes_url}

点击链接查看完整转写内容"""

    try:
        result = api.send_text_message(config.chat_id, message)
        if result.get("code") == 0:
            print(f"   消息发送成功")
        else:
            print(f"   消息发送失败: {result.get('msg')}")
    except Exception as e:
        print(f"   消息发送异常: {e}")

    # 下载转写文字
    print(f"\n   步骤 3/3: 下载会议转写文字...")

    try:
        transcript = scraper.fetch(
            minutes_url,
            debug=debug,
            custom_selector=custom_selector
        )

        if not transcript or len(transcript.strip()) < 10:
            print("   抓取到的转写文字过短，可能未正确加载页面")
            return False

        filepath = scraper.save(transcript, title, config.save_dir)
        print(f"   转写文字已保存: {filepath}")
        print(f"   字数: {len(transcript)} 字符")
        return True

    except RuntimeError as e:
        print(f"   {e}")
        return False
    except Exception as e:
        print(f"   下载转写文字失败: {e}")
        return False


if __name__ == "__main__":
    sys.exit(main())
