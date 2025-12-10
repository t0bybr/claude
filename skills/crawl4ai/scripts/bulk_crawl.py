#!/usr/bin/env python3
"""
Phase 1: Bulk Crawler

Crawls an entire website recursively and saves:
- Raw HTML for each page
- Raw Markdown from crawl4ai
- Metadata JSON
- Internal links for processing

This creates a complete snapshot that can be post-processed offline.
"""

import asyncio
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse, urljoin
from datetime import datetime
import hashlib
import aiohttp
from bs4 import BeautifulSoup
import re


class BulkCrawler:
    def __init__(self, start_url: str, output_dir: str = "crawled_site",
                 max_depth: int = 3, wait_time: float = 5.0,
                 same_domain_only: bool = True, download_assets: bool = False):
        self.start_url = start_url
        self.output_dir = output_dir
        self.max_depth = max_depth
        self.wait_time = wait_time
        self.same_domain_only = same_domain_only
        self.download_assets = download_assets

        self.base_domain = urlparse(start_url).netloc
        self.visited = set()
        self.to_crawl = [(start_url, 0)]  # (url, depth)
        self.crawl_results = []

    def _should_crawl(self, url: str, depth: int) -> bool:
        """Check if URL should be crawled."""
        if url in self.visited:
            return False

        if depth > self.max_depth:
            return False

        if self.same_domain_only:
            if urlparse(url).netloc != self.base_domain:
                return False

        # Skip common non-content URLs
        skip_patterns = [
            'javascript:', 'mailto:', 'tel:', '#',
            '.pdf', '.zip', '.jpg', '.png', '.gif', '.svg',
            'login', 'logout', 'signin', 'signup',
        ]

        url_lower = url.lower()
        if any(pattern in url_lower for pattern in skip_patterns):
            return False

        return True

    def _url_to_path(self, url: str) -> str:
        """Convert URL to filesystem path, preserving directory structure."""
        parsed = urlparse(url)

        # Create path from URL path - KEEP slashes as directories!
        path = parsed.path.strip('/')
        if not path:
            path = 'index'

        # Add query string to path if present
        if parsed.query:
            query_hash = hashlib.md5(parsed.query.encode()).hexdigest()[:8]
            path = f"{path}/query_{query_hash}"

        # Remove trailing slashes and add /index for directory-like URLs
        if path.endswith('/'):
            path = path.rstrip('/') + '/index'

        return path

    async def download_asset(self, url: str, page_dir: Path) -> dict:
        """Download an asset (image or file) and save it."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        return None

                    content = await response.read()
                    content_type = response.headers.get('Content-Type', '')

                    # Generate hash as filename (shortened to 16 chars)
                    full_hash = hashlib.sha256(content).hexdigest()
                    file_hash = full_hash[:16]

                    # Determine asset type and extension
                    if 'image' in content_type.lower():
                        asset_type = 'images'
                        ext = self._get_image_extension(content_type)
                    elif 'pdf' in content_type.lower():
                        asset_type = 'files'
                        ext = '.pdf'
                    else:
                        asset_type = 'files'
                        ext = self._get_extension_from_url(url)

                    # Create assets directory
                    assets_dir = page_dir / 'assets' / asset_type
                    assets_dir.mkdir(parents=True, exist_ok=True)

                    # Filename
                    filename = f"{file_hash}{ext}"

                    # Save asset
                    asset_file = assets_dir / filename
                    with open(asset_file, 'wb') as f:
                        f.write(content)

                    # Save metadata
                    metadata = {
                        'hash': file_hash,
                        'filename': filename,
                        'original_url': url,
                        'size': len(content),
                        'mime_type': content_type,
                        'downloaded_at': datetime.now().isoformat(),
                    }

                    # Add image dimensions if it's an image
                    if asset_type == 'images':
                        try:
                            from PIL import Image
                            import io
                            img = Image.open(io.BytesIO(content))
                            metadata['width'] = img.width
                            metadata['height'] = img.height
                        except:
                            pass  # Skip if PIL not available or image can't be opened

                    meta_file = assets_dir / f"{file_hash}.json"
                    with open(meta_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)

                    return metadata

        except Exception as e:
            print(f"   ⚠️  Asset download failed: {url} - {e}")
            return None

    def _get_image_extension(self, content_type: str) -> str:
        """Get image extension from content type."""
        extensions = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'image/svg+xml': '.svg',
        }
        return extensions.get(content_type.lower(), '.jpg')

    def _get_extension_from_url(self, url: str) -> str:
        """Get file extension from URL."""
        parsed = urlparse(url)
        path = parsed.path
        if '.' in path:
            return path[path.rfind('.'):]
        return '.bin'

    async def download_media_from_crawl4ai(self, media_dict: dict, html: str, page_dir: Path) -> dict:
        """Download media extracted by crawl4ai."""
        if not self.download_assets:
            return {'images': [], 'files': []}

        image_hashes = []
        file_hashes = []

        # Download images from crawl4ai's media extraction
        if media_dict and 'images' in media_dict:
            for img_info in media_dict['images']:
                src = img_info.get('src', '')
                if not src:
                    continue

                # Make absolute URL
                abs_url = urljoin(self.start_url, src)

                metadata = await self.download_asset(abs_url, page_dir)
                if metadata:
                    # Add crawl4ai metadata
                    metadata['alt_text'] = img_info.get('alt', '')
                    if img_info.get('width'):
                        metadata['width'] = img_info['width']
                    if img_info.get('height'):
                        metadata['height'] = img_info['height']

                    # Re-save metadata with additional info
                    assets_dir = page_dir / 'assets' / 'images'
                    meta_file = assets_dir / f"{metadata['hash']}.json"
                    with open(meta_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)

                    image_hashes.append(metadata['hash'])

        # Find PDFs manually from HTML (crawl4ai doesn't extract these)
        soup = BeautifulSoup(html, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.endswith('.pdf') or 'pdf' in href.lower():
                abs_url = urljoin(self.start_url, href)
                metadata = await self.download_asset(abs_url, page_dir)
                if metadata:
                    # Update metadata with link text
                    metadata['link_text'] = link.get_text(strip=True)
                    # Re-save metadata with link text
                    assets_dir = page_dir / 'assets' / 'files'
                    meta_file = assets_dir / f"{metadata['hash']}.json"
                    with open(meta_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)

                    file_hashes.append(metadata['hash'])

        return {
            'images': image_hashes,
            'files': file_hashes
        }

    async def crawl_page(self, url: str) -> dict:
        """Crawl a single page and return results."""
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

        print(f"📥 Crawling: {url}")

        browser_config = BrowserConfig(headless=True, verbose=False)

        # Exclude common non-content elements
        excluded_selector = 'nav, header, footer, aside, .nav, .menu, .navigation, .header, .footer, .sidebar'

        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=60000,
            excluded_selector=excluded_selector,
            js_code=f"await new Promise(resolve => setTimeout(resolve, {int(self.wait_time * 1000)}))"
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=crawler_config)

            if not result.success:
                print(f"   ❌ Failed: {result.error_message}")
                return None

            return {
                'url': url,
                'html': result.html,
                'markdown': result.markdown,
                'metadata': result.metadata or {},
                'links': result.links.get('internal', []) if result.links else [],
                'media': result.media if hasattr(result, 'media') else {'images': [], 'videos': [], 'audios': []},
                'success': True,
                'crawled_at': datetime.now().isoformat()
            }

    async def crawl_batch(self, urls: list) -> list:
        """Crawl multiple URLs in parallel."""
        if not urls:
            return []

        print(f"\n🚀 Crawling batch of {len(urls)} pages in parallel...")

        # Crawl all URLs in parallel
        tasks = [self.crawl_page(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and None results
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                print(f"   ⚠️  Exception: {result}")
            elif result and result.get('success'):
                valid_results.append(result)

        return valid_results

    async def save_result(self, result: dict):
        """Save crawl result to disk in clean structure."""
        url = result['url']
        path_name = self._url_to_path(url)

        # Create directory for this page
        page_dir = Path(self.output_dir) / path_name
        page_dir.mkdir(parents=True, exist_ok=True)

        # Save HTML (for reference/debugging)
        html_file = page_dir / 'raw.html'
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(result['html'])

        # Save raw markdown from crawl4ai
        raw_md_file = page_dir / 'raw.md'
        with open(raw_md_file, 'w', encoding='utf-8') as f:
            f.write(result['markdown'])

        # Download assets if enabled (use crawl4ai's media extraction)
        assets_info = await self.download_media_from_crawl4ai(result['media'], result['html'], page_dir)

        # Save minimal metadata - will be enriched by post-processing
        metadata = {
            'crawled_at': result['crawled_at'],
            'url': result['url'],
            'title': result['metadata'].get('title', 'Untitled'),
            # Will be enriched by post-processing:
            # - content_hash
            # - language
            # - estimated_tokens
            # - description
            # - keywords
            # - image_hashes (if assets downloaded)
            # - file_hashes (if assets downloaded)
        }

        # Add assets info if downloaded (hashes already shortened to 16 chars)
        # Use list() to preserve order but remove duplicates
        if self.download_assets:
            # Remove duplicates while preserving order
            seen = set()
            unique_images = []
            for h in assets_info['images']:
                if h not in seen:
                    seen.add(h)
                    unique_images.append(h)

            seen = set()
            unique_files = []
            for h in assets_info['files']:
                if h not in seen:
                    seen.add(h)
                    unique_files.append(h)

            metadata['image_hashes'] = unique_images
            metadata['file_hashes'] = unique_files

        meta_file = page_dir / 'metadata.json'
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        assets_msg = ""
        if self.download_assets:
            assets_msg = f" + {len(assets_info['images'])} images, {len(assets_info['files'])} files"

        print(f"   ✓ Saved to {page_dir}{assets_msg}")

    def extract_new_links(self, result: dict, current_depth: int):
        """Extract new links to crawl from result."""
        for link in result.get('links', []):
            url = link.get('href')
            if not url:
                continue

            # Make absolute URL
            if not url.startswith('http'):
                url = urljoin(result['url'], url)

            # Remove fragment
            url = url.split('#')[0]

            if self._should_crawl(url, current_depth + 1):
                self.to_crawl.append((url, current_depth + 1))

    async def crawl(self):
        """Execute the bulk crawl."""
        print(f"🚀 Bulk Crawl startet: {self.start_url}")
        print(f"   📁 Output: {self.output_dir}")
        print(f"   🌲 Max Depth: {self.max_depth}")
        print(f"   🌐 Same Domain Only: {self.same_domain_only}")
        print()

        while self.to_crawl:
            # Get all URLs at current depth
            current_batch = []
            remaining = []

            for url, depth in self.to_crawl:
                if url not in self.visited:
                    current_batch.append((url, depth))
                    self.visited.add(url)
                else:
                    remaining.append((url, depth))

            self.to_crawl = remaining

            if not current_batch:
                break

            # Group by depth for better output
            by_depth = {}
            for url, depth in current_batch:
                if depth not in by_depth:
                    by_depth[depth] = []
                by_depth[depth].append(url)

            # Crawl each depth level
            for depth in sorted(by_depth.keys()):
                urls = by_depth[depth]
                print(f"📊 Depth {depth}: {len(urls)} pages")

                # Crawl in parallel
                results = await self.crawl_batch(urls)

                # Save results and extract links
                for result in results:
                    await self.save_result(result)

                    # Extract links for next iteration
                    current_url = result['url']
                    current_depth = depth
                    self.extract_new_links(result, current_depth)

        # Save crawl summary
        summary = {
            'start_url': self.start_url,
            'crawled_at': datetime.now().isoformat(),
            'total_pages': len(self.visited),
            'max_depth': self.max_depth,
            'pages': list(self.visited)
        }

        summary_file = Path(self.output_dir) / 'crawl_summary.json'
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Crawl abgeschlossen!")
        print(f"   📄 Total: {len(self.visited)} Seiten")
        print(f"   📁 Output: {self.output_dir}")


async def main():
    parser = argparse.ArgumentParser(
        description='Phase 1: Bulk website crawler - crawls entire site and saves raw data'
    )
    parser.add_argument('url', help='Start URL to crawl')
    parser.add_argument('--output-dir', default='crawled_site',
                       help='Output directory (default: crawled_site)')
    parser.add_argument('--max-depth', type=int, default=3,
                       help='Maximum crawl depth (default: 3)')
    parser.add_argument('--wait-time', type=float, default=5.0,
                       help='JavaScript wait time in seconds (default: 5.0)')
    parser.add_argument('--allow-external', action='store_true',
                       help='Allow crawling external domains')
    parser.add_argument('--download-assets', action='store_true',
                       help='Download all images and PDF files')

    args = parser.parse_args()

    crawler = BulkCrawler(
        start_url=args.url,
        output_dir=args.output_dir,
        max_depth=args.max_depth,
        wait_time=args.wait_time,
        same_domain_only=not args.allow_external,
        download_assets=args.download_assets
    )

    await crawler.crawl()


if __name__ == '__main__':
    asyncio.run(main())
