import os
import sys
import json
import time
import shutil
import random
import argparse
import subprocess
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

# Setup Logger
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:7}</level> | {message}")
logger.add(os.path.join(LOG_DIR, "wakeup.log"), rotation="10 MB", encoding="utf-8",
           format="{time:YYYY-MM-DD HH:mm:ss} | {level:7} | {message}")

def find_cswap_binary():
    """Find the cswap binary in PATH or fall back to standard local bin paths."""
    binary = shutil.which("cswap")
    if binary:
        return binary
    home = os.path.expanduser("~")
    fallbacks = [
        os.path.join(home, ".local", "bin", "cswap"),
        os.path.join(home, ".local", "bin", "claude-swap"),
    ]
    for path in fallbacks:
        if os.path.exists(path):
            return path
    return "cswap"

CSWAP_BIN = find_cswap_binary()

def load_config():
    """Load configuration parameters from config.json."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config.json: {str(e)}. Using defaults.")
        return {
            "schedule_time": "05:00",
            "wake_up_prompt": "Hello Claude, wake up check. Please reply with 'OK' only.",
            "jitter_min": 30,
            "jitter_max": 120
        }

def get_cswap_accounts():
    """Fetch the list of registered Claude Code accounts from cswap."""
    try:
        result = subprocess.run([CSWAP_BIN, "list", "--json"], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return data.get("accounts", [])
    except Exception as e:
        logger.error(f"Failed to fetch accounts from cswap: {str(e)}")
        return []

async def wake_up_account(account, prompt):
    """Wake up a single account by sending a non-interactive prompt using cswap run."""
    acc_num = account.get("number")
    email = account.get("email")
    alias = account.get("alias", "")
    
    label = f"#{acc_num} ({email})" if not alias else f"#{acc_num} ({alias} - {email})"
    logger.info(f"Starting wake-up check for {label}")
    
    cmd = [CSWAP_BIN, "run", str(acc_num), "--", prompt]
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
            rc = proc.returncode
        except asyncio.TimeoutError:
            proc.kill()
            stdout, stderr = await proc.communicate()
            raise Exception("Command execution timed out after 60 seconds")
            
        if rc == 0:
            logger.success(f"Successfully woke up {label}!")
            preview = stdout.decode('utf-8', errors='replace').strip()
            preview_clean = ' '.join(preview.split())[:100]
            logger.info(f"[{label}] Response preview: {preview_clean}...")
        else:
            err_msg = stderr.decode('utf-8', errors='replace').strip()
            raise Exception(f"Command returned exit code {rc}. Error: {err_msg}")
            
    except Exception as e:
        logger.error(f"Failed to wake up {label}: {str(e)}")

async def run_wake_up_process():
    """Execute the wake-up cycle for all registered accounts with jitter delay."""
    logger.info("Starting daily wake-up cycle...")
    config = load_config()
    accounts = get_cswap_accounts()
    
    if not accounts:
        logger.warning("No accounts found in cswap. Please run 'cswap add' to add accounts first.")
        return
        
    logger.info(f"Found {len(accounts)} accounts to process.")
    
    for idx, acc in enumerate(accounts):
        jitter_min = config.get("jitter_min", 30)
        jitter_max = config.get("jitter_max", 120)
        
        if idx > 0 and jitter_max > 0:
            delay = random.randint(jitter_min, jitter_max)
            logger.info(f"Waiting for {delay} seconds before processing next account (jitter)...")
            await asyncio.sleep(delay)
            
        await wake_up_account(acc, config.get("wake_up_prompt"))
        
    logger.info("Wake-up cycle completed.")

async def main():
    parser = argparse.ArgumentParser(description="Claude Code Multi-Account Wake-up Scheduler")
    parser.add_argument("--now", action="store_true", help="Run the wake-up cycle immediately and exit")
    args = parser.parse_args()
    
    if args.now:
        logger.info("Running manual wake-up trigger (--now)...")
        await run_wake_up_process()
        logger.info("Manual execution finished.")
        return

    config = load_config()
    time_str = config.get("schedule_time", "05:00")
    try:
        hour, minute = map(int, time_str.split(":"))
    except ValueError:
        logger.error(f"Invalid schedule_time format: '{time_str}'. Expected 'HH:MM'. Falling back to 05:00.")
        hour, minute = 5, 0

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_wake_up_process,
        trigger='cron',
        hour=hour,
        minute=minute,
        name="daily_claude_wakeup"
    )
    
    scheduler.start()
    logger.info(f"Daily wake-up scheduled at {hour:02d}:{minute:02d} local time.")
    logger.info("Scheduler running. Press Ctrl+C to exit.")
    
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutting down gracefully...")
        scheduler.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
