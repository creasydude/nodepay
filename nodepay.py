import asyncio
import aiohttp
import time
import uuid
import cloudscraper  # 引入 cloudscraper
from loguru import logger


def show_copyright():
    copyright_info = """
    *****************************************************
    *           Version 1.0                             *
    *           Copyright (c) 2024                      *
    *           All Rights Reserved                     *
    *****************************************************
    """
    print(copyright_info)

    confirm = input("Press Enter to continue or Ctrl+C to exit... ")

    if confirm.strip() == "":
        print("Continuing with the program...")
    else:
        print("Exiting the program.")
        exit()


# Constants
PING_INTERVAL = 60  # 每分钟发送一次请求
RETRIES = 60  # 全局重试计数
TOKEN_FILE = 'np_tokens.txt'  # 令牌文件名

DOMAIN_API = {
    "SESSION": "https://api.nodepay.org/api/auth/session",
    "PING": "https://nw.nodepay.org/api/network/ping"
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES["NONE_CONNECTION"]
browser_id = None
account_info = {}
last_ping_time = time.time()


def uuidv4():
    return str(uuid.uuid4())


def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp


async def render_profile_info(token):
    global browser_id, account_info

    try:
        np_session_info = load_session_info()

        if not np_session_info:
            # 生成新的 browser_id
            browser_id = uuidv4()
            response = await call_api(DOMAIN_API["SESSION"], {}, token)
            valid_resp(response)
            account_info = response["data"]
            if account_info.get("uid"):
                save_session_info(account_info)
                await start_ping(token)
            else:
                handle_logout()
        else:
            account_info = np_session_info
            await start_ping(token)
    except Exception as e:
        logger.error(f"Error in render_profile_info: {e}")


async def call_api(url, data, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://app.nodepay.ai",
    }

    try:
        # 使用 cloudscraper 创建会话
        scraper = cloudscraper.create_scraper()

        # 使用 cloudscraper 发起请求
        response = scraper.post(url, json=data, headers=headers, timeout=10)

        # 检查响应状态码
        response.raise_for_status()
        return valid_resp(response.json())
    except Exception as e:
        logger.error(f"Error during API call: {e}")
        raise ValueError(f"Failed API call to {url}")


async def start_ping(token):
    try:
        while True:
            await ping(token)
            await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        logger.info("Ping task was cancelled")
    except Exception as e:
        logger.error(f"Error in start_ping: {e}")


async def ping(token):
    global last_ping_time, RETRIES, status_connect

    current_time = time.time()

    # 检查是否距离上次ping已经过去了指定的间隔
    if (current_time - last_ping_time) < PING_INTERVAL:
        logger.info("Skipping ping, not enough time elapsed")
        return

    # 更新上次ping的时间
    last_ping_time = current_time

    try:
        data = {
            "id": account_info.get("uid"),
            "browser_id": browser_id,
            "timestamp": int(time.time())
        }

        response = await call_api(DOMAIN_API["PING"], data, token)
        if response["code"] == 0:
            logger.info(f"Ping successful: {response}")
            RETRIES = 0
            status_connect = CONNECTION_STATES["CONNECTED"]
        else:
            handle_ping_fail(response)
    except Exception as e:
        logger.error(f"Ping failed: {e}")
        handle_ping_fail(None)


def handle_ping_fail(response):
    global RETRIES, status_connect

    RETRIES += 1
    if response and response.get("code") == 403:
        handle_logout()
    elif RETRIES < 2:
        status_connect = CONNECTION_STATES["DISCONNECTED"]
    else:
        status_connect = CONNECTION_STATES["DISCONNECTED"]


def handle_logout():
    global status_connect, account_info

    status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    account_info = {}
    logger.info("Logged out and cleared session info")


def load_tokens_from_file(filename):
    try:
        with open(filename, 'r') as file:
            tokens = file.read().splitlines()
        return tokens
    except Exception as e:
        logger.error(f"Failed to load tokens: {e}")
        raise SystemExit("Exiting due to failure in loading tokens")


def save_session_info(data):
    pass  # 这里可以添加保存逻辑，例如写入文件或数据库


def load_session_info():
    return {}  # 这里可以加载会话信息


async def main():
    tokens = load_tokens_from_file(TOKEN_FILE)

    while True:
        for token in tokens:
            task = asyncio.create_task(render_profile_info(token))
            await asyncio.wait([task], return_when=asyncio.FIRST_COMPLETED)
            await asyncio.sleep(10)

# 主程序入口
if __name__ == '__main__':
    show_copyright()
    print("Welcome to the main program!")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
