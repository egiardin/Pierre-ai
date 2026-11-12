"""API publique : await extract_site(url). Une seule URL, sortie locale indépendante."""

import asyncio
from datetime import datetime, timezone
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, urljoin, urldefrag
from .network import fetch, resolve_public
from .catalog import Catalog

MAX_PAGES = 24
MAX_CANDIDATES = 1500
MAX_REQUESTS = 1800
MAX_BYTES = 350_000_000
MAX_SECONDS = 600
PRIORITY = (
    "galerie",
    "gallery",
    "photo",
    "chambre",
    "room",
    "suite",
    "spa",
    "restaurant",
    "service",
    "contact",
)
EXTENSIONS = re.compile(r"\.(pdf|zip|jpe?g|png|webp|avif|svg|mp4|css|js)(?:$|\?)", re.I)


def normalize(url):
    p = urlsplit(urldefrag(url)[0])
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("URL HTTP(S) complète requise")
    return urlunsplit((p.scheme, p.netloc, p.path or "/", p.query, ""))


def rank(url):
    path = urlsplit(url).path.lower()
    return next((i for i, term in enumerate(PRIORITY) if term in path), len(PRIORITY))


class BudgetExceeded(RuntimeError):
    pass


class Collector:
    def __init__(self, url, folder):
        self.url = url
        self.folder = folder
        self.catalog = Catalog(folder)
        self.candidates = {}
        self.pages = []
        self.events = []
        self.started = time.monotonic()
        self.requests = 0
        self.network_bytes = 0
        self.limit = None
        self.gate = asyncio.Semaphore(3)

    def check(self):
        if time.monotonic() - self.started >= MAX_SECONDS:
            self.limit = "temps_600_secondes"
        elif self.network_bytes >= MAX_BYTES:
            self.limit = "volume_350_Mo"
        elif self.requests >= MAX_REQUESTS:
            self.limit = "requetes_1800"
        if self.limit:
            raise BudgetExceeded(self.limit)

    async def download(self, url, max_bytes):
        async with self.gate:
            self.check()
            self.requests += 1
            result = await asyncio.to_thread(
                fetch, url, min(max_bytes, MAX_BYTES - self.network_bytes)
            )
            self.network_bytes += len(result[0])
            return result

    def candidate(self, url, page, kind, alt=""):
        try:
            url = normalize(url)
        except ValueError:
            return
        if url not in self.candidates and len(self.candidates) >= MAX_CANDIDATES:
            marker = {"stage": "limit", "reason": "1500_candidates_maximum"}
            if marker not in self.events:
                self.events.append(marker)
            return
        source = {"page": page, "kind": kind, "alt": alt, "url": url}
        rows = self.candidates.setdefault(url, [])
        if source not in rows:
            rows.append(source)

    async def sitemap(self, base):
        queue = [urljoin(base, "/sitemap.xml")]
        links = []
        for _ in range(4):
            if not queue:
                break
            url = queue.pop(0)
            try:
                raw, _, _ = await self.download(url, 2_000_000)
                root = ET.fromstring(raw)
                locations = [
                    e.text
                    for e in root.iter()
                    if e.tag.split("}")[-1] == "loc" and e.text
                ]
                if root.tag.split("}")[-1] == "sitemapindex":
                    queue.extend(
                        x
                        for x in locations[:20]
                        if urlsplit(x).hostname == urlsplit(base).hostname
                    )
                else:
                    links.extend(locations[:300])
            except BudgetExceeded:
                raise
            except Exception as e:
                self.events.append({"stage": "sitemap", "reason": type(e).__name__})
        return links

    async def browser_route(self, route):
        req = route.request
        if req.method != "GET" or req.resource_type in ("media", "font", "websocket"):
            await route.abort()
            return
        if req.resource_type == "image":
            self.candidate(req.url, req.frame.url, "network")
            # Découverte d'abord ; évite de télécharger toutes les variantes pour le rendu.
            await route.abort()
            return
        try:
            raw, mime, final = await self.download(req.url, 4_000_000)
            # Conserver la destination de navigation dans le navigateur après vérification.
            if final != req.url and req.is_navigation_request():
                await route.fulfill(status=302, headers={"location": final})
            else:
                await route.fulfill(
                    status=200,
                    body=raw,
                    content_type=mime or "application/octet-stream",
                )
        except BudgetExceeded:
            await route.abort()
        except Exception as e:
            self.events.append({"stage": "resource", "reason": type(e).__name__})
            await route.abort()

    async def snapshot(self, page, script):
        data = await page.evaluate(script)
        for asset in data["assets"]:
            self.candidate(asset["url"], page.url, asset["kind"], asset["alt"])
        return data

    async def crawl(self):
        from playwright.async_api import async_playwright

        script = Path(__file__).with_name("discover.js").read_text()
        queue = [self.url]
        visited = set()
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True, args=["--disable-dev-shm-usage"]
            )
            try:
                context = await browser.new_context(
                    service_workers="block",
                    accept_downloads=False,
                    viewport={"width": 1440, "height": 1000},
                    locale="fr-FR",
                )
                await context.route("**/*", self.browser_route)
                await context.route_web_socket("**/*", lambda ws: ws.close())
                page = await context.new_page()
                page.set_default_timeout(2500)
                allowed = {urlsplit(self.url).hostname}
                while queue and len(visited) < MAX_PAGES:
                    self.check()
                    current = queue.pop(0)
                    if current in visited:
                        continue
                    visited.add(current)
                    print(
                        f"[pages {len(visited)}/{MAX_PAGES}] {urlsplit(current).path}",
                        flush=True,
                    )
                    try:
                        await page.goto(
                            current, wait_until="domcontentloaded", timeout=35000
                        )
                        if len(visited) == 1:
                            allowed.add(urlsplit(page.url).hostname)
                        elif urlsplit(page.url).hostname not in allowed:
                            continue
                        await page.wait_for_timeout(700)
                        data = await self.snapshot(page, script)
                        # Refus de cookies uniquement, pas de soumission ni bouton de réservation.
                        for label in ("Tout refuser", "Refuser", "Reject all"):
                            button = page.get_by_role("button", name=label, exact=True)
                            if await button.count() == 1 and await button.is_visible():
                                await button.click()
                                break
                        for _ in range(12):
                            self.check()
                            at_end = await page.evaluate("""() => {
                              window.scrollBy(0,900);
                              return window.scrollY+innerHeight>=document.documentElement.scrollHeight-5;
                            }""")
                            await page.wait_for_timeout(150)
                            data = await self.snapshot(page, script)
                            if at_end:
                                break
                        # Avancer uniquement les contrôles de carrousel identifiés.
                        controls = page.locator(
                            '.swiper-button-next, .slick-next, button[aria-label="Next slide"], button[aria-label="Diapositive suivante"]'
                        )
                        for i in range(min(await controls.count(), 3)):
                            for _ in range(4):
                                try:
                                    control = controls.nth(i)
                                    if not await control.is_visible():
                                        break
                                    await control.click(timeout=800)
                                    await page.wait_for_timeout(200)
                                    await self.snapshot(page, script)
                                except Exception:
                                    break
                        self.pages.append(
                            {
                                "url": page.url,
                                "title": data["title"],
                                "description": data["description"],
                                "text": data["text"],
                                "anchors": data.get("anchors") or [],
                            }
                        )
                        links = data["links"]
                        if len(visited) == 1:
                            links += await self.sitemap(page.url)
                        for link in links:
                            try:
                                link = normalize(link)
                            except ValueError:
                                continue
                            if (
                                urlsplit(link).hostname in allowed
                                and not EXTENSIONS.search(link)
                                and link not in visited
                                and link not in queue
                                and len(queue) < 500
                            ):
                                queue.append(link)
                        queue.sort(key=rank)
                    except BudgetExceeded:
                        raise
                    except Exception as e:
                        self.events.append(
                            {
                                "stage": "page",
                                "url": current,
                                "reason": type(e).__name__,
                            }
                        )
                if queue:
                    self.events.append({"stage": "limit", "reason": "24_pages_maximum"})
            finally:
                await browser.close()

    async def collect_photos(self):
        # Les variantes HD explicitement liées et srcset sont essayées avant currentSrc.
        order = {
            "linked-original": 0,
            "srcset": 1,
            "data-full": 1,
            "data-large": 1,
            "currentSrc": 3,
            "network": 4,
        }
        urls = sorted(
            self.candidates,
            key=lambda u: min(order.get(s["kind"], 2) for s in self.candidates[u]),
        )
        for i, url in enumerate(urls):
            self.check()
            if len(self.catalog.photos) >= 99:
                self.events.append(
                    {
                        "stage": "limit",
                        "reason": "99_photos_maximum",
                        "unexamined": len(urls) - i,
                    }
                )
                break
            sources = self.candidates[url]
            try:
                raw, _, _ = await self.download(url, 12_000_000)
                result = self.catalog.ingest(raw, sources[0])
                if result in ("saved", "duplicate"):
                    # ingest établit le regroupement pixels ; ajouter les autres provenances.
                    photo = (
                        self.catalog.photos[-1]
                        if result == "saved"
                        else next(
                            p for p in self.catalog.photos if sources[0] in p["sources"]
                        )
                    )
                    for source in sources[1:]:
                        if source not in photo["sources"]:
                            photo["sources"].append(source)
                print(
                    f"[photos {len(self.catalog.photos)}/99] candidate {i+1}/{len(urls)} : {result}",
                    flush=True,
                )
            except BudgetExceeded:
                raise
            except Exception as e:
                self.catalog.reject(sources[0], "download_failed")
                self.catalog.rejected[-1][
                    "detail"
                ] = f"{type(e).__name__}: {str(e)[:240]}"

    def report(self, status):
        return {
            "schema_version": 1,
            "source_url": self.url,
            "status": status,
            "limit": self.limit,
            "elapsed_seconds": round(time.monotonic() - self.started, 1),
            "network_bytes": self.network_bytes,
            "requests": self.requests,
            "page_count": len(self.pages),
            "pages": self.pages,
            "candidate_count": len(self.candidates),
            "candidates": self.candidates,
            "events": self.events,
            "warning": "Contenus et pertinence des photos à confirmer par le propriétaire.",
        }


async def extract_site(url: str) -> Path:
    """Prend uniquement l'URL. Retourne le dossier contenant report.json et gallery.html."""
    url = normalize(url)
    await asyncio.to_thread(resolve_public, url)
    host = re.sub(r"[^a-zA-Z0-9.-]", "_", urlsplit(url).hostname)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = Path("extractions") / f"{host}-{stamp}"
    collector = Collector(url, folder)
    status = "complete_within_limits"
    try:
        # Réserver une partie du budget à la collecte des photos après la découverte.
        try:
            await asyncio.wait_for(collector.crawl(), timeout=330)
        except asyncio.TimeoutError:
            collector.events.append(
                {"stage": "limit", "reason": "decouverte_330_secondes"}
            )
            status = "partial"
        if not collector.pages:
            raise RuntimeError("Aucune page exploitable récupérée")
        await asyncio.wait_for(
            collector.collect_photos(),
            timeout=max(1, MAX_SECONDS - (time.monotonic() - collector.started)),
        )
    except asyncio.CancelledError:
        status = "interrupted"
        raise
    except (BudgetExceeded, asyncio.TimeoutError):
        status = "partial"
        collector.events.append(
            {"stage": "limit", "reason": collector.limit or "temps_maximum"}
        )
    except Exception as e:
        status = "failed"
        collector.events.append(
            {"stage": "fatal", "reason": type(e).__name__, "message": str(e)[:300]}
        )
    finally:
        collector.catalog.write(collector.report(status))
    print(
        f"Résultat : {folder.resolve()} — {len(collector.catalog.photos)} photos — {status}",
        flush=True,
    )
    if status == "failed":
        raise RuntimeError(f"Extraction échouée ; consulter {folder}/report.json")
    return folder.resolve()
