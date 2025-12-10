#!/usr/bin/env python3
"""
Smart website crawler that intelligently identifies and extracts main content.

Two-stage approach:
1. Download HTML and analyze structure to find main content area
2. Extract only the main content using CSS selectors
3. Post-process and clean the result
"""

import asyncio
import argparse
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import hashlib
from datetime import datetime
from collections import defaultdict


class SmartCrawler:
    def __init__(self, url: str, output_dir: str = "crawled_site", wait_time: float = 5.0):
        self.url = url
        self.output_dir = output_dir
        self.wait_time = wait_time
        self.base_domain = urlparse(url).netloc

    async def analyze_html_structure(self, html: str) -> dict:
        """Analyze HTML to find the main content area."""
        soup = BeautifulSoup(html, 'html.parser')

        print("🔍 Analysiere HTML-Struktur...")

        # Strategy 1: Look for semantic HTML5 tags
        main_tag = soup.find('main')
        article_tag = soup.find('article')

        # Strategy 2: Look for common content IDs/classes
        content_candidates = []
        for tag in soup.find_all(['div', 'section', 'main', 'article']):
            tag_id = tag.get('id', '').lower()
            tag_class = ' '.join(tag.get('class', [])).lower()

            # Check for content-related names
            if any(keyword in tag_id or keyword in tag_class for keyword in
                   ['content', 'main', 'article', 'inhalt', 'body', 'post']):
                content_candidates.append(tag)

        # Strategy 3: Find elements with high text-to-link ratio
        scored_elements = []
        for candidate in content_candidates if content_candidates else soup.find_all(['div', 'section', 'article']):
            text = candidate.get_text(strip=True)
            links = candidate.find_all('a')

            if len(text) > 200:  # Minimum text length
                text_length = len(text)
                link_text_length = sum(len(link.get_text(strip=True)) for link in links)
                link_count = len(links)

                # Score: prefer lots of text, fewer links
                score = text_length - (link_count * 20) - (link_text_length * 0.5)

                tag_info = {
                    'tag': candidate.name,
                    'id': candidate.get('id', ''),
                    'class': ' '.join(candidate.get('class', [])),
                    'score': score,
                    'text_length': text_length,
                    'link_count': link_count
                }
                scored_elements.append(tag_info)

        # Sort by score
        scored_elements.sort(key=lambda x: x['score'], reverse=True)

        # Build CSS selector for best candidate
        best_selector = None
        if main_tag:
            best_selector = 'main'
            print("   ✓ Gefunden: <main> Tag")
        elif article_tag:
            best_selector = 'article'
            print("   ✓ Gefunden: <article> Tag")
        elif scored_elements:
            best = scored_elements[0]
            if best['id']:
                best_selector = f"#{best['id']}"
                print(f"   ✓ Gefunden: Element mit ID '{best['id']}'")
            elif best['class']:
                # Use first class
                first_class = best['class'].split()[0]
                best_selector = f".{first_class}"
                print(f"   ✓ Gefunden: Element mit Klasse '{first_class}'")

        # Identify navigation/header/footer to exclude
        exclude_selectors = []
        for tag in soup.find_all(['nav', 'header', 'footer']):
            if tag.get('id'):
                exclude_selectors.append(f"#{tag.get('id')}")
            elif tag.get('class'):
                first_class = tag.get('class')[0]
                exclude_selectors.append(f".{first_class}")

        # Also exclude common menu patterns
        for tag in soup.find_all(['div', 'ul'], class_=re.compile(r'(menu|nav|navigation)', re.I)):
            if tag.get('class'):
                first_class = tag.get('class')[0]
                if f".{first_class}" not in exclude_selectors:
                    exclude_selectors.append(f".{first_class}")

        print(f"   ℹ  Haupt-Selektor: {best_selector or 'body (fallback)'}")
        if exclude_selectors:
            print(f"   ℹ  Ausgeschlossen: {', '.join(exclude_selectors[:5])}")

        return {
            'content_selector': best_selector or 'body',
            'exclude_selectors': exclude_selectors[:10],  # Limit to avoid over-filtering
            'scored_elements': scored_elements[:5]  # Top 5 for reference
        }

    async def crawl_with_selector(self, selector: str, exclude_tags: list) -> dict:
        """Crawl page using specific CSS selector."""
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

        print(f"📥 Lade Seite mit Selektor: {selector}")

        browser_config = BrowserConfig(
            headless=True,
            verbose=False
        )

        # Build exclusion list for crawl4ai
        excluded_selector = ', '.join(exclude_tags) if exclude_tags else None

        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=60000,
            css_selector=selector,  # Use crawl4ai's CSS selector feature
            excluded_selector=excluded_selector,  # Exclude nav/header/footer
            js_code=f"await new Promise(resolve => setTimeout(resolve, {int(self.wait_time * 1000)}))"
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(
                url=self.url,
                config=crawler_config
            )

            if not result.success:
                raise Exception(f"Crawl fehlgeschlagen: {result.error_message}")

            return {
                'markdown': result.markdown,
                'html': result.html,
                'metadata': result.metadata or {},
                'links': result.links.get('internal', []) if result.links else []
            }

    def clean_markdown(self, markdown: str) -> str:
        """Post-process and clean the markdown content."""
        print("🧹 Bereinige Markdown...")

        lines = markdown.split('\n')
        cleaned_lines = []
        prev_line = ""

        skip_patterns = [
            r'^\s*\[.*menu.*\].*$',  # Menu links
            r'^\s*\[.*nav.*\].*$',   # Navigation links
            r'^\s*open submenu',     # Submenu controls
            r'^\s*close submenu',    # Submenu controls
            r'^\s*\+\s*$',           # Plus symbols
            r'^\s*-\s*$',            # Minus symbols
            r'^\s*×\s*$',            # Close symbols
            r'^\s*zoom',             # Zoom controls
            r'^\s*\[prev\]',         # Prev/Next links
            r'^\s*\[next\]',
            r'^\s*\[start\]',
            r'^\s*\[stop\]',
            r'^\s*slider',           # Slider controls
            r'gehe zum',             # "Gehe zum..." links
            r'zur startseite',       # "Zur Startseite" links
            r'^\s*\[zur.{0,2}ck\]',  # Zurück link (with encoding issues)
            r'^\s*\[weiter\]',       # Weiter link
            r'^\s*\[\d+\]\(',        # Pagination number links like [1]( [2]( etc
            r'^\s*\d+\|',            # Lines starting with number| (pagination)
            r'^\s*\[alle .*aufrufen',  # "Alle ... aufrufen" links
        ]

        seen_chunks = set()  # Track larger text chunks to avoid big duplicates

        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Skip lines matching patterns
            if any(re.search(pattern, line_lower) for pattern in skip_patterns):
                continue

            # Skip duplicate lines
            if line.strip() == prev_line.strip() and line.strip():
                continue

            # Skip excessive empty lines
            if not line.strip() and not cleaned_lines[-1].strip() if cleaned_lines else False:
                continue

            # Check for duplicate sections (e.g., event listings)
            # Look at chunks of 5 lines to detect repeated sections
            if i + 5 < len(lines):
                chunk = ''.join(lines[i:i+5]).strip()
                if chunk in seen_chunks and len(chunk) > 50:
                    # Skip this line as it's part of a duplicate section
                    continue
                if len(chunk) > 50:
                    seen_chunks.add(chunk)

            cleaned_lines.append(line)
            prev_line = line

        # Remove excessive whitespace
        cleaned = '\n'.join(cleaned_lines)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        return cleaned.strip()

    def _create_frontmatter(self, markdown: str, metadata: dict) -> str:
        """Create YAML frontmatter."""
        timestamp = datetime.now().isoformat()
        content_hash = hashlib.sha256(markdown.encode()).hexdigest()

        title = metadata.get('title', 'Untitled')

        # Generate description from content
        description = self._generate_description(markdown)

        # Extract keywords
        keywords = self._extract_keywords(markdown, title)

        # Detect language
        language = "de" if len(re.findall(r'[äöüßÄÖÜ]', markdown)) > 10 else "en"

        # Estimate tokens
        token_estimate = len(markdown.split()) * 1.3

        frontmatter = [
            "---",
            f"crawled_at: {timestamp}",
            f"url: {self.url}",
            f"title: \"{title.replace('"', '\\"')}\"",
            f"content_hash: {content_hash}",
            f"language: {language}",
            f"estimated_tokens: {int(token_estimate)}",
            f"description: \"{description.replace('"', '\\"')}\"",
        ]

        if keywords:
            frontmatter.append("keywords:")
            for kw in keywords[:10]:
                frontmatter.append(f"  - {kw}")

        frontmatter.append("---")
        frontmatter.append("")

        return '\n'.join(frontmatter)

    def _generate_description(self, markdown: str) -> str:
        """Generate description from markdown content."""
        # Remove headers and formatting
        text = re.sub(r'^#+\s+', '', markdown, flags=re.MULTILINE)
        text = re.sub(r'[*_`\[\]]', '', text)

        # Find first substantial paragraph
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        for line in lines:
            if len(line) >= 50:
                if len(line) <= 200:
                    return line
                else:
                    truncated = line[:197]
                    last_space = truncated.rfind(' ')
                    if last_space > 0:
                        return truncated[:last_space] + '...'
                    return truncated + '...'

        # Fallback
        clean_text = ' '.join(lines)
        if len(clean_text) <= 200:
            return clean_text
        else:
            truncated = clean_text[:197]
            last_space = truncated.rfind(' ')
            if last_space > 0:
                return truncated[:last_space] + '...'
            return truncated + '...'

    def _extract_keywords(self, content: str, title: str) -> list:
        """Extract keywords from content."""
        text = f"{title} {content}".lower()
        text = re.sub(r'[#*`\[\]()]', ' ', text)
        words = re.findall(r'\b[a-zäöüß]{4,}\b', text)

        word_freq = defaultdict(int)
        for word in words:
            word_freq[word] += 1

        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:10]]

    async def crawl(self):
        """Execute the smart crawl process."""
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

        print(f"🚀 Smart Crawl startet: {self.url}\n")

        # Stage 1: Download HTML and analyze
        print("📊 Stufe 1: HTML-Analyse")
        browser_config = BrowserConfig(headless=True, verbose=False)
        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=60000,
            js_code=f"await new Promise(resolve => setTimeout(resolve, {int(self.wait_time * 1000)}))"
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=self.url, config=crawler_config)

            if not result.success:
                raise Exception(f"Fehler beim Laden: {result.error_message}")

            analysis = await self.analyze_html_structure(result.html)

        # Stage 2: Extract content with selector
        print("\n📝 Stufe 2: Inhalts-Extraktion")
        content_result = await self.crawl_with_selector(
            analysis['content_selector'],
            analysis['exclude_selectors']
        )

        # Stage 3: Clean markdown
        print("\n✨ Stufe 3: Nachbearbeitung")
        cleaned_markdown = self.clean_markdown(content_result['markdown'])

        # Create frontmatter
        frontmatter = self._create_frontmatter(cleaned_markdown, content_result['metadata'])

        # Combine and save
        final_content = frontmatter + '\n\n' + cleaned_markdown

        # Save to file
        import os
        os.makedirs(self.output_dir, exist_ok=True)
        output_file = os.path.join(self.output_dir, 'index.md')

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_content)

        print(f"\n✅ Gespeichert: {output_file}")
        print(f"   📊 Token-Schätzung: {int(len(cleaned_markdown.split()) * 1.3)}")
        print(f"   📏 Zeichen: {len(cleaned_markdown)}")


async def main():
    parser = argparse.ArgumentParser(description='Smart website crawler')
    parser.add_argument('url', help='URL to crawl')
    parser.add_argument('--output-dir', default='crawled_site_smart', help='Output directory')
    parser.add_argument('--wait-time', type=float, default=5.0, help='JavaScript wait time in seconds')

    args = parser.parse_args()

    crawler = SmartCrawler(
        url=args.url,
        output_dir=args.output_dir,
        wait_time=args.wait_time
    )

    await crawler.crawl()


if __name__ == '__main__':
    asyncio.run(main())
