"""飞书妙记转写文字抓取器（基于 Playwright）"""

import json
import os
import time

from playwright.sync_api import sync_playwright


class TranscriptScraper:
    """使用浏览器自动化抓取妙记页面的转写文字"""

    # 飞书妙记页面中转写文字的候选 CSS 选择器
    SELECTORS = [
        '[class*="speaker-line"]',
        '[class*="speaker-box"]',
        '.transcript-content [class*="speaker"]',
        '.transcript-content [class*="ace-line"]',
        '.paragraphs-container [class*="ace-line"]',
        '.transcript-content [class*="paragraph"]',
        '[class*="transcript"] [class*="paragraph"]',
        '[class*="minutes-transcript"] p',
        '[class*="subtitle"] [class*="text"]',
        '[class*="speech-to-text"] p',
        '.minutes-content p',
        '.content p',
        '[data-testid="transcript-paragraph"]',
        '[data-testid="minute-text"]',
    ]

    def __init__(self, cookie_file: str = "./cookies/lark_cookies.json", headless: bool = True):
        self.cookie_file = cookie_file
        self.headless = headless
        self.cookies_dir = os.path.dirname(cookie_file) or "."

    def _load_cookies(self, context) -> bool:
        """从文件加载 cookie"""
        if os.path.exists(self.cookie_file):
            with open(self.cookie_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            return True
        return False

    def _save_cookies(self, context) -> None:
        """保存 cookie 到文件"""
        cookies = context.cookies()
        os.makedirs(self.cookies_dir, exist_ok=True)
        with open(self.cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

    def _is_login_page(self, page) -> bool:
        """检查当前是否在登录页面"""
        url = page.url
        return "login" in url or "passport" in url or "auth" in url

    def _switch_to_transcript_view(self, page) -> None:
        """切换到"文字记录"视图（转写文字）"""
        try:
            time.sleep(2)

            # 方法1：通过文字内容点击"文字记录"按钮
            transcript_btn = page.query_selector('text=文字记录')
            if transcript_btn:
                has_transcript = page.evaluate('''() => {
                    return document.querySelectorAll('.transcript-paragraph-item').length > 0;
                }''')
                if has_transcript:
                    print("   当前已在文字记录视图")
                    return

                print("   点击'文字记录'按钮切换到转写视图...")
                transcript_btn.click()
                for i in range(10):
                    time.sleep(1)
                    has_items = page.evaluate('''() => {
                        return document.querySelectorAll('.transcript-paragraph-item').length > 0;
                    }''')
                    if has_items:
                        print(f"   转写文字已加载（等待 {i+1}s）")
                        time.sleep(2)
                        return
                print("   等待转写文字加载超时")
                return

            # 方法2：尝试通过 class 名找到标签按钮
            tab_selectors = [
                '[class*="transcript-tab"]',
                '[class*="subtitle-tab"]',
                '[class*="text-tab"]',
            ]
            for selector in tab_selectors:
                tab = page.query_selector(selector)
                if tab:
                    cls = tab.get_attribute('class') or ''
                    if 'hidden' not in cls and 'inactive' not in cls:
                        print(f"   使用选择器 '{selector}' 切换到转写视图")
                        tab.click()
                        time.sleep(6)
                        return

            print("   未找到'文字记录'按钮，尝试直接抓取当前视图内容")
        except Exception as e:
            print(f"   切换视图时出错: {e}，尝试直接抓取")

    def fetch(self, minutes_url: str, debug: bool = False, custom_selector: str = "") -> str:
        """抓取妙记页面的转写文字"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless, channel="chrome")
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )

            has_cookies = self._load_cookies(context)
            page = context.new_page()

            print(f"   正在打开妙记页面: {minutes_url}")
            page.goto(minutes_url, wait_until="networkidle", timeout=60000)

            # 检查是否需要登录
            if not has_cookies or self._is_login_page(page):
                if self.headless:
                    browser.close()
                    raise RuntimeError(
                        "需要登录飞书。请使用 --no-headless 模式首次运行，"
                        "手动登录后 cookie 会自动保存。"
                    )
                print("   检测到登录页面，请在浏览器中手动登录...")
                print("   程序会自动检测登录状态并继续（最多等待60秒）")

                max_wait = 60
                waited = 0
                while self._is_login_page(page) and waited < max_wait:
                    time.sleep(2)
                    waited += 2
                    try:
                        page.reload(wait_until="networkidle", timeout=10000)
                    except Exception:
                        pass
                    print(f"   等待登录中... ({waited}s/{max_wait}s)")

                if self._is_login_page(page):
                    print("   等待超时，可能未成功登录")
                    browser.close()
                    raise RuntimeError("登录超时，请重新运行")
                print("   已检测到已登录")

            # 保存 cookie
            self._save_cookies(context)
            print("   Cookie 已保存")

            # 等待页面动态内容加载
            page.wait_for_load_state("networkidle")
            time.sleep(3)

            # 尝试切换到"文字记录"视图
            self._switch_to_transcript_view(page)

            # 调试模式
            if debug:
                self._save_debug_snapshot(page)

            # 抓取转写文字
            transcript = self._extract_transcript(page, custom_selector)

            browser.close()
            return transcript

    def _extract_transcript(self, page, custom_selector: str = "") -> str:
        """从页面提取转写文字（含说话人和时间戳）"""

        # 优先使用 JavaScript 提取结构化数据
        js_result = self._extract_via_javascript(page)
        if js_result:
            return js_result

        # 备选：CSS 选择器
        selectors = [custom_selector] if custom_selector else self.SELECTORS

        for selector in selectors:
            if not selector:
                continue
            try:
                elements = page.query_selector_all(selector)
                if elements:
                    texts = []
                    seen = set()
                    for el in elements:
                        text = el.inner_text().strip()
                        if text and len(text) > 3:
                            if text not in seen:
                                seen.add(text)
                                texts.append(text)
                    if texts:
                        print(f"   使用选择器 '{selector}' 成功抓取 {len(texts)} 段文字（去重后）")
                        return "\n\n".join(texts)
            except Exception:
                continue

        # 兜底方案
        print("   未能使用已知选择器抓取，尝试兜底方案...")
        return self._fallback_extract(page)

    def _extract_via_javascript(self, page) -> str:
        """使用 JavaScript 在页面上提取转写文字（含说话人和时间戳）"""
        try:
            self._scroll_to_load_all(page)

            result = page.evaluate("""
                () => {
                    const entries = [];
                    const seenKeys = new Set();

                    function extractItem(item) {
                        const nameEl = item.querySelector('.p-user-name-editable');
                        let speaker = '';
                        if (nameEl) {
                            speaker = nameEl.getAttribute('user-name-content') || '';
                            if (!speaker) {
                                try {
                                    const style = window.getComputedStyle(nameEl, '::before');
                                    speaker = style.content.replace(/['"]/g, '');
                                } catch(e) {}
                            }
                        }

                        const timeEl = item.querySelector('.p-time');
                        let timestamp = '';
                        if (timeEl) {
                            timestamp = timeEl.getAttribute('time-content') || '';
                            if (!timestamp) {
                                try {
                                    const style = window.getComputedStyle(timeEl, '::before');
                                    timestamp = style.content.replace(/['"]/g, '');
                                } catch(e) {}
                            }
                        }

                        let text = '';
                        const contentEl = item.querySelector('.mm-paragraph-content');
                        if (contentEl) {
                            text = contentEl.innerText.trim();
                        }
                        if (!text) {
                            const editor = item.querySelector('.paragraph-content-editor');
                            if (editor) text = editor.innerText.trim();
                        }

                        return { speaker, timestamp, text };
                    }

                    const items = document.querySelectorAll('.transcript-paragraph-item');
                    for (const item of items) {
                        const data = extractItem(item);
                        if (data.text && data.text.length > 3) {
                            const key = data.speaker + '|' + data.timestamp + '|' + data.text.substring(0, 50);
                            if (!seenKeys.has(key)) {
                                seenKeys.add(key);
                                entries.push(data);
                            }
                        }
                    }

                    return { entries, method: 'transcript-paragraphs', count: entries.length };
                }
            """)

            if result and result.get('entries') and len(result['entries']) > 0:
                entries = result['entries']
                lines = []
                for item in entries:
                    speaker = item.get('speaker', '')
                    timestamp = item.get('timestamp', '')
                    text = item.get('text', '')
                    if speaker and timestamp:
                        lines.append(f"{speaker} {timestamp}\n{text}")
                    elif speaker:
                        lines.append(f"{speaker}\n{text}")
                    elif timestamp:
                        lines.append(f"{timestamp}\n{text}")
                    else:
                        lines.append(text)

                print(f"   JavaScript 提取 {len(lines)} 段发言（含说话人和时间戳）")
                return "\n\n".join(lines)
        except Exception as e:
            print(f"   JavaScript 提取失败: {e}")

        return ""

    def _scroll_to_load_all(self, page) -> None:
        """滚动虚拟列表加载所有发言条目"""
        try:
            page.evaluate("""
                () => {
                    const listContainer = document.querySelector('.rc-virtual-list-holder')
                        || document.querySelector('.transcript-paragraph-item')?.closest('[class*="virtual"]')
                        || document.querySelector('.detail-right-content');

                    if (!listContainer) return;

                    let lastH = listContainer.scrollHeight;
                    let stableCount = 0;
                    for (let i = 0; i < 30 && stableCount < 3; i++) {
                        listContainer.scrollTop = listContainer.scrollHeight;
                        const t = performance.now();
                        while (performance.now() - t < 150) {}
                        if (listContainer.scrollHeight === lastH) {
                            stableCount++;
                        } else {
                            stableCount = 0;
                            lastH = listContainer.scrollHeight;
                        }
                    }
                    listContainer.scrollTop = 0;
                }
            """)
            time.sleep(1)
        except Exception:
            pass

    def _fallback_extract(self, page) -> str:
        """兜底提取方案"""
        content_selectors = ["main", "article", "[role='main']", ".content", "#content", "body"]

        for selector in content_selectors:
            element = page.query_selector(selector)
            if element:
                text = element.inner_text().strip()
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                meaningful_lines = [line for line in lines if len(line) > 5]
                if meaningful_lines:
                    return "\n\n".join(meaningful_lines)

        return page.inner_text("body").strip()

    def _save_debug_snapshot(self, page) -> None:
        """保存调试快照"""
        debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")
        os.makedirs(debug_dir, exist_ok=True)

        html_path = os.path.join(debug_dir, "page.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"   调试：页面HTML已保存到 {html_path}")

        screenshot_path = os.path.join(debug_dir, "page.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"   调试：页面截图已保存到 {screenshot_path}")

    def save(self, content: str, filename: str, save_dir: str = "./meeting_transcripts") -> str:
        """保存转写文字到本地文件"""
        os.makedirs(save_dir, exist_ok=True)

        safe_filename = "".join(
            c for c in filename if c.isalnum() or c in (" ", "-", "_", ".", "(", ")", "【", "】", "（", "）")
        ).strip()
        if not safe_filename.endswith(".txt"):
            safe_filename += ".txt"

        filepath = os.path.join(save_dir, safe_filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath
