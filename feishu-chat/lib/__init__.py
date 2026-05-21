"""飞书群聊消息抓取 Skill

通过飞书 Open API 抓取群聊消息并保存到本地文件。

使用方式:
    python3 chat_logger_v2.py                          # 抓取所有配置群的消息
    python3 chat_logger_v2.py --chat-id oc_xxx         # 抓取指定群
    python3 chat_logger_v2.py --hours 24               # 只抓取最近24小时
    python3 chat_logger_v2.py --download-images        # 同时下载图片
    python3 chat_logger_v2.py --format json            # 输出为JSON格式
"""
