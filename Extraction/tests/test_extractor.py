import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from pierre_extract.catalog import Catalog
from pierre_extract.extractor import Collector, normalize, rank, BudgetExceeded
from pierre_extract.network import resolve_public, UnsafeURL


def picture(color="red", size=(600, 400), fmt="JPEG"):
    data = io.BytesIO()
    Image.new("RGB", size, color).save(data, format=fmt)
    return data.getvalue()


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.catalog = Catalog(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_deduplication_and_provenance(self):
        source = {
            "url": "https://hotel.example/a.jpg",
            "page": "https://hotel.example",
            "alt": "Piscine",
            "kind": "img",
        }
        self.assertEqual(self.catalog.ingest(picture(), source), "saved")
        self.assertEqual(
            self.catalog.ingest(
                picture(), dict(source, page="https://hotel.example/spa")
            ),
            "duplicate",
        )
        self.assertEqual(len(self.catalog.photos), 1)
        self.assertEqual(len(self.catalog.photos[0]["sources"]), 2)

    def test_less_than_100(self):
        for i in range(105):
            self.catalog.ingest(
                picture(color=(i, 40, 100), fmt="PNG"),
                {"url": str(i), "alt": "", "page": "", "kind": "img"},
            )
        self.assertEqual(len(self.catalog.photos), 99)
        self.assertEqual(len(self.catalog.rejected), 6)

    def test_invalid_small_and_html_escape(self):
        self.assertEqual(
            self.catalog.ingest(b"not image", {}), "image_invalide_ou_trop_grande"
        )
        self.assertEqual(
            self.catalog.ingest(picture(size=(32, 32)), {}), "petit_media_ou_icone"
        )
        self.catalog.ingest(picture(), {"alt": "<script>alert(1)</script>"})
        self.catalog.write({"pages": []})
        self.assertNotIn(
            "<script>", (Path(self.temp.name) / "gallery.html").read_text()
        )
        self.assertEqual(
            json.loads((Path(self.temp.name) / "report.json").read_text())[
                "photo_count"
            ],
            1,
        )

    def test_same_decoded_pixels_different_format(self):
        # Deux fichiers PNG aux mêmes pixels : une seule photo.
        self.catalog.ingest(picture(fmt="PNG"), {"url": "a"})
        self.assertEqual(
            self.catalog.ingest(picture(fmt="PNG"), {"url": "b"}), "duplicate"
        )

    def test_scope_ranking(self):
        self.assertLess(rank("https://x/galerie"), rank("https://x/legal"))
        self.assertEqual(normalize("https://x/fr/#section"), "https://x/fr/")
        with self.assertRaises(ValueError):
            normalize("file:///etc/passwd")

    def test_private_network_block(self):
        with patch(
            "socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]
        ):
            with self.assertRaises(UnsafeURL):
                resolve_public("https://example.com")

    def test_budget(self):
        collector = Collector("https://hotel.example", Path(self.temp.name) / "run")
        collector.requests = 1800
        with self.assertRaises(BudgetExceeded):
            collector.check()

    def test_download_limit_and_failures(self):
        async def run():
            collector = Collector("https://hotel.example", Path(self.temp.name) / "run")
            collector.candidate(
                "https://hotel.example/a", "https://hotel.example", "img"
            )
            collector.candidate(
                "https://hotel.example/b", "https://hotel.example", "img"
            )

            async def fake(url, limit):
                if url.endswith("/b"):
                    raise ValueError("invalid")
                return picture(), "image/jpeg", url

            collector.download = fake
            await collector.collect_photos()
            self.assertEqual(len(collector.catalog.photos), 1)
            self.assertEqual(collector.catalog.rejected[0]["reason"], "download_failed")

        asyncio.run(run())


class BrowserTests(unittest.TestCase):
    def test_browser_html_css_srcset_lazy_and_text(self):
        async def run(folder):
            collector = Collector("https://hotel.example/", folder)
            html = """<html><head><title>Hôtel test</title><style>
            .hero {height:100px;background-image:url('/background.jpg')}
            </style></head><body><h1>Chambres et spa</h1>
            <div class="hero"></div><picture><source srcset="/large.jpg 1600w, /small.jpg 400w">
            <img src="/normal.jpg" data-src="/lazy.jpg" alt="Chambre"></picture>
            <a href="/original.jpg">Original</a><script>
            setTimeout(()=>{let x=new Image();x.src='/dynamic.jpg';document.body.append(x)},50)
            </script></body></html>"""

            def fake(url, limit):
                if "sitemap" in url:
                    return b"<urlset/>", "application/xml", url
                return html.encode(), "text/html", url

            with patch("pierre_extract.extractor.fetch", side_effect=fake):
                await collector.crawl()
            urls = set(collector.candidates)
            for name in [
                "background",
                "large",
                "small",
                "normal",
                "lazy",
                "original",
                "dynamic",
            ]:
                self.assertIn(f"https://hotel.example/{name}.jpg", urls)
            self.assertIn("Chambres et spa", collector.pages[0]["text"])

        with tempfile.TemporaryDirectory() as folder:
            asyncio.run(run(Path(folder)))


if __name__ == "__main__":
    unittest.main()
