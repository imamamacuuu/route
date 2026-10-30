import asyncio
import logging
import re
import time
from typing import Dict, List, Optional, Any
import aiohttp
from .config import PROXY_SOURCES

logger = logging.getLogger("route.proxy")
IP_PORT_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b")

class ProxyPool:
    def __init__(self):
        self.proxies: List[Dict[str, Any]] = []
        self._index = 0
        self._lock = asyncio.Lock()
        self.last_scraped = 0
        self.is_scraping = False

    def count(self) -> int:
        return len(self.proxies)

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self.proxies)

    async def get_proxy(self) -> Optional[str]:
        async with self._lock:
            if not self.proxies:
                return None
            proxy = self.proxies[self._index % len(self.proxies)]
            self._index = (self._index + 1) % len(self.proxies)
            return proxy["url"]

    async def get_current(self) -> Optional[Dict[str, Any]]:
        async with self._lock:
            if not self.proxies:
                return None
            return dict(self.proxies[self._index % len(self.proxies)])

    async def rotate(self) -> Optional[Dict[str, Any]]:
        async with self._lock:
            if not self.proxies:
                return None
            self._index = (self._index + 1) % len(self.proxies)
            return dict(self.proxies[self._index])

    async def mark_success(self, proxy_url: str):
        # ponytail: simple in-memory counter reset, upgrade to redis if multi-worker
        async with self._lock:
            for p in self.proxies:
                if p["url"] == proxy_url:
                    p["fails"] = 0
                    break

    async def mark_bad(self, proxy_url: str):
        async with self._lock:
            for p in list(self.proxies):
                if p["url"] == proxy_url:
                    p["fails"] += 1
                    if p["fails"] >= 2:
                        logger.warning(f"Evicting dead proxy: {proxy_url}")
                        self.proxies.remove(p)
                        if self.proxies:
                            self._index = self._index % len(self.proxies)
                        else:
                            self._index = 0
                    break

    async def add_validated_proxy(self, url: str, latency: float, ip: str):
        async with self._lock:
            if not any(p["url"] == url for p in self.proxies):
                self.proxies.append({
                    "url": url,
                    "latency": round(latency, 1),
                    "ip": ip,
                    "fails": 0,
                    "added_at": time.time()
                })
                self.proxies.sort(key=lambda x: x["latency"])

    async def validate_candidate(self, session: aiohttp.ClientSession, ip_port: str, sem: asyncio.Semaphore) -> Optional[Dict[str, Any]]:
        proxy_url = f"http://{ip_port}"
        t0 = time.perf_counter()
        # Validate HTTPS CONNECT tunnel specifically since AI upstreams are HTTPS
        test_url = "https://cloudflare.com/cdn-cgi/trace"
        timeout = aiohttp.ClientTimeout(total=2.5, connect=1.8)
        async with sem:
            try:
                async with session.get(test_url, proxy=proxy_url, timeout=timeout, ssl=False) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        latency = (time.perf_counter() - t0) * 1000
                        ip = ip_port.split(":")[0]
                        for line in text.splitlines():
                            if line.startswith("ip="):
                                ip = line.split("=", 1)[1].strip()
                                break
                        return {"url": proxy_url, "latency": latency, "ip": ip}
            except Exception:
                pass
        return None

    async def harvest(self):
        if self.is_scraping:
            return
        self.is_scraping = True
        logger.info("[Petani-Proxy] Harvesting candidate HTTPS proxies from public feeds...")
        candidates = set()

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            for source in PROXY_SOURCES:
                try:
                    async with session.get(source) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            matches = IP_PORT_REGEX.findall(text)
                            candidates.update(matches)
                except Exception as e:
                    logger.debug(f"Failed scraping {source}: {e}")

            cand_list = list(candidates)[:200]
            logger.info(f"[Petani-Proxy] Validating {len(cand_list)} candidates via HTTPS CONNECT (sem=20)...")
            sem = asyncio.Semaphore(20)
            tasks = [self.validate_candidate(session, cand, sem) for cand in cand_list]

            results = await asyncio.gather(*tasks, return_exceptions=True)
            added = 0
            for r in results:
                if isinstance(r, dict) and r:
                    await self.add_validated_proxy(r["url"], r["latency"], r["ip"])
                    added += 1

            self.last_scraped = time.time()
            logger.info(f"[Petani-Proxy] Harvest complete! Added {added} live HTTPS proxies. Total pool: {len(self.proxies)}")
        self.is_scraping = False

    async def background_worker(self):
        await self.harvest()
        while True:
            await asyncio.sleep(90)
            try:
                if len(self.proxies) < 5 or (time.time() - self.last_scraped > 600):
                    await self.harvest()
            except Exception as e:
                logger.error(f"[Petani-Proxy] Background worker error: {e}")

proxy_pool = ProxyPool()
