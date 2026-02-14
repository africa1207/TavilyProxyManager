"""
SOCKS5 Proxy Pool Manager
管理 SOCKS5 代理池，支持代理轮换、连通性测试、禁用列表持久化
"""
import json
import os
import random
import time
import requests


class Socks5PoolManager:
    """SOCKS5 代理池管理器"""

    def __init__(self, config: dict, base_dir: str = None):
        """
        Args:
            config: 配置字典，包含 SOCKS5_ENABLED, SOCKS5_FILE 等
            base_dir: 基础目录（默认为脚本目录）
        """
        self.enabled = config.get("SOCKS5_ENABLED", False)
        self.proxy_file = config.get("SOCKS5_FILE", "socks5.txt")
        self.test_timeout = config.get("SOCKS5_TEST_TIMEOUT", 10)
        self.max_per_round = config.get("SOCKS5_REGISTRATIONS_PER_PROXY", 3)
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))

        # 状态
        self.proxies: list[str] = []           # 规范化的代理列表
        self.banned: set[str] = set()          # 已禁用
        self.round_used: dict[str, int] = {}   # 本轮使用计数（内存）
        self.shuffled_queue: list[str] = []    # shuffle bag

        # 持久化路径
        self.stats_file = os.path.join(self.base_dir, "socks5_stats.json")
        self.banned_file = os.path.join(self.base_dir, "banned_socks5.txt")

        if self.enabled:
            self._load_proxies()
            self._load_banned()

    def _load_proxies(self):
        """从文件加载代理列表"""
        path = os.path.join(self.base_dir, self.proxy_file)
        if not os.path.exists(path):
            raise FileNotFoundError(f"[PROXY] 代理文件不存在: {path}")

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # 取空格前的部分（去掉注释）
                proxy_part = line.split()[0]
                normalized = self._normalize_proxy(proxy_part)
                if normalized and normalized not in self.proxies:
                    self.proxies.append(normalized)

        print(f"[PROXY] 加载 {len(self.proxies)} 个代理")

    def _normalize_proxy(self, raw: str) -> str | None:
        """规范化代理格式"""
        raw = raw.strip()
        if not raw:
            return None
        # 跳过 http/https 代理（不是 socks5）
        if raw.startswith("http://") or raw.startswith("https://"):
            print(f"[PROXY] 警告: 跳过非 SOCKS5 代理 {raw}")
            return None
        # 检测并修复 socks5://http://ip:port 这种错误格式
        if raw.startswith("socks5://http://") or raw.startswith("socks5://https://"):
            print(f"[PROXY] 警告: 跳过无效格式 {raw}")
            return None
        # 如果没有 socks5:// 前缀，添加
        if not raw.startswith("socks5://") and not raw.startswith("socks5h://"):
            # 检查是否是 ip:port 格式
            if ":" in raw:
                raw = f"socks5://{raw}"
            else:
                print(f"[PROXY] 警告: 无效格式 {raw}")
                return None
        return raw

    def _load_banned(self):
        """加载禁用列表"""
        if not os.path.exists(self.banned_file):
            return
        with open(self.banned_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # 规范化格式后再加入（跳过无效的 http/https 代理）
                    normalized = self._normalize_proxy(line)
                    if normalized:
                        self.banned.add(normalized)
        if self.banned:
            print(f"[PROXY] 加载 {len(self.banned)} 个已禁用代理")

    def reset_round_counts(self):
        """重置本轮使用计数"""
        self.round_used.clear()
        self.shuffled_queue.clear()
        print(f"[PROXY] 已重置本轮使用计数")

    def get_proxy(self) -> str | None:
        """获取一个可用代理（shuffle bag 算法）"""
        if not self.enabled:
            return None

        # 筛选可用代理
        available = [
            p for p in self.proxies
            if p not in self.banned
            and self.round_used.get(p, 0) < self.max_per_round
        ]

        if not available:
            # 检查是否所有代理都用完本轮配额
            non_banned = [p for p in self.proxies if p not in self.banned]
            if non_banned and all(self.round_used.get(p, 0) >= self.max_per_round for p in non_banned):
                self.reset_round_counts()
                available = non_banned

        if not available:
            print(f"[PROXY] 所有代理不可用，降级到系统代理")
            return None

        # Shuffle bag: 如果队列空了，重新 shuffle
        self.shuffled_queue = [p for p in self.shuffled_queue if p in available]
        if not self.shuffled_queue:
            self.shuffled_queue = available.copy()
            random.shuffle(self.shuffled_queue)

        proxy = self.shuffled_queue.pop(0)
        print(f"[PROXY] 从代理池选择: {proxy}")
        return proxy

    def test_connectivity(self, proxy: str) -> bool:
        """测试代理连通性，失败则自动 ban"""
        test_url = "https://app.tavily.com"
        start = time.time()
        try:
            resp = requests.get(
                test_url,
                proxies={"http": proxy, "https": proxy},
                timeout=self.test_timeout
            )
            elapsed = time.time() - start
            # 严格判断：2xx/3xx/403 算成功，4xx(除403)/5xx 算失败
            success = resp.status_code < 400 or resp.status_code == 403
            if success:
                print(f"[PROXY] 连通性测试: 成功 (耗时 {elapsed:.1f}s)")
            else:
                print(f"[PROXY] 连通性测试: 失败 status={resp.status_code} (耗时 {elapsed:.1f}s)")
                self.mark_banned(proxy, reason=f"connectivity-failed-{resp.status_code}")
            return success
        except Exception as e:
            elapsed = time.time() - start
            print(f"[PROXY] 连通性测试失败: {e} (耗时 {elapsed:.1f}s)")
            self.mark_banned(proxy, reason=f"connectivity-error: {e}")
            return False

    def mark_used(self, proxy: str):
        """标记代理使用+1"""
        self.round_used[proxy] = self.round_used.get(proxy, 0) + 1
        count = self.round_used[proxy]
        print(f"[PROXY] 注册成功，代理使用计数: {count}/{self.max_per_round}")
        self._save_stats(proxy, success=True)

    def mark_banned(self, proxy: str, reason: str = ""):
        """标记代理被禁"""
        # 规范化格式
        normalized = self._normalize_proxy(proxy)
        if not normalized:
            return
        if normalized in self.banned:
            return
        self.banned.add(normalized)
        print(f"[PROXY] 代理被禁，标记到禁用列表: {normalized}")

        # 追加到文件
        with open(self.banned_file, "a", encoding="utf-8") as f:
            f.write(f"{normalized}\n")

        self._save_stats(normalized, banned=True, reason=reason)

    def _save_stats(self, proxy: str, success: bool = False, banned: bool = False, reason: str = ""):
        """保存统计信息到 JSON"""
        stats = {}
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    stats = json.load(f)
            except Exception:
                stats = {}

        if proxy not in stats:
            stats[proxy] = {"total_success": 0, "banned": False}

        if success:
            stats[proxy]["total_success"] = stats[proxy].get("total_success", 0) + 1
        if banned:
            stats[proxy]["banned"] = True
            stats[proxy]["ban_reason"] = reason
            stats[proxy]["ban_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

        # 原子写入
        tmp_file = self.stats_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, self.stats_file)
