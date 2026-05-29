import schedule
import threading
import json
import time
from datetime import datetime
from pathlib import Path


class AutoScheduler:
    """每日定时自动扫描调度器"""

    def __init__(self, config_path=".scheduler_config.json"):
        self.config_path = Path(config_path)
        self.enabled = False
        self.time_str = "09:00"  # 默认执行时间
        self.job = None
        self.thread = None
        self.running = False
        self.callback = None  # 执行任务的回调函数
        self._load_config()

    def _load_config(self):
        """从配置文件加载调度设置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                self.enabled = config.get("enabled", False)
                self.time_str = config.get("time", "09:00")
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduler config loaded: enabled={self.enabled}, time={self.time_str}")
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduler config load error: {e}")

    def _save_config(self):
        """保存调度设置到配置文件"""
        # 读取现有配置以保留 scan_config
        existing = {}
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass
        config = {
            "enabled": self.enabled,
            "time": self.time_str,
            "scan_config": existing.get("scan_config", {}),
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def save_scan_config(self, scan_config: dict):
        """保存扫描相关配置（工作目录、扫描天数、LLM设置等）到配置文件"""
        # 读取现有配置
        existing = {}
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass
        existing["scan_config"] = scan_config
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_scan_config(self) -> dict:
        """从配置文件读取扫描相关配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                return config.get("scan_config", {})
            except Exception:
                pass
        return {}

    def set_callback(self, callback):
        """设置执行任务的回调函数"""
        self.callback = callback

    def set_schedule(self, enabled, time_str):
        """设置调度配置"""
        self.enabled = enabled
        self.time_str = time_str
        self._save_config()

        if enabled:
            self.start()
        else:
            self.stop()

    def start(self):
        """启动调度"""
        if self.running:
            self.stop()

        if not self.enabled:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduler not started: enabled=False")
            return

        schedule.clear()
        schedule.every().day.at(self.time_str).do(self._run_job)

        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduler started, will run daily at {self.time_str}")

    def stop(self):
        """停止调度"""
        self.running = False
        schedule.clear()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)

    def _run_scheduler(self):
        """运行调度器（后台线程）"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduler thread started, checking every 60s")
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次

    def _run_job(self):
        """执行定时任务"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Auto scan job triggered at scheduled time: {self.time_str}")
        if self.callback:
            try:
                self.callback()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Auto scan completed successfully")
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Auto scan error: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Auto scan skipped: no callback set")

    def get_status(self):
        """获取当前状态"""
        return {
            "enabled": self.enabled,
            "time": self.time_str,
            "running": self.running
        }
