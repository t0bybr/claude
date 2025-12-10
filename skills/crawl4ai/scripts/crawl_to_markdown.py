#!/usr/bin/env python3
"""
Smart website crawler that intelligently identifies and extracts main content.

Three-stage approach:
1. Download HTML and analyze structure to find main content area
2. Extract only the main content using CSS selectors
3. Post-process and clean the result
"""

import asyncio
import argparse
import re
import os
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import hashlib
from datetime import datetime
from collections import defaultdict
import json
import aiohttp
from pathlib import Path


class SmartCrawler:
    def __init__(self, url: str, output_dir: str = "crawled_site", wait_time: float = 5.0,
                 download_assets: bool = False, interactive: bool = False,
                 generate_alt_texts: bool = False, quality_check: bool = False):
        self.url = url
        self.output_dir = output_dir
        self.wait_time = wait_time
        self.base_domain = urlparse(url).netloc
        self.download_assets = download_assets
        self.interactive = interactive
        self.generate_alt_texts = generate_alt_texts
        self.quality_check = quality_check
        self.downloaded_assets = {
            'images': [],
            'files': []
        }

    def analyze_html_structure(self, html: str) -> dict:
        """Analyze HTML to find the main content area. Returns elements to keep/exclude."""
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
        main_content_element = None

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
                    'link_count': link_count,
                    'element': candidate  # Store actual element
                }
                scored_elements.append(tag_info)

        # Sort by score
        scored_elements.sort(key=lambda x: x['score'], reverse=True)

        # Identify main content element
        if main_tag:
            main_content_element = main_tag
            print("   ✓ Gefunden: <main> Tag")
        elif article_tag:
            main_content_element = article_tag
            print("   ✓ Gefunden: <article> Tag")
        elif scored_elements:
            main_content_element = scored_elements[0]['element']
            best = scored_elements[0]
            if best['id']:
                print(f"   ✓ Gefunden: Element mit ID '{best['id']}'")
            elif best['class']:
                print(f"   ✓ Gefunden: Element mit Klasse '{best['class'].split()[0]}'")

        # Identify elements to exclude (navigation, headers, footers)
        exclude_elements = set()
        for tag in soup.find_all(['nav', 'header', 'footer']):
            exclude_elements.add(tag)

        # Also exclude common menu patterns
        for tag in soup.find_all(['div', 'ul'], class_=re.compile(r'(menu|nav|navigation)', re.I)):
            exclude_elements.add(tag)

        print(f"   ℹ  Main-Content: {main_content_element.name if main_content_element else 'body'}")
        print(f"   ℹ  Ausgeschlossen: {len(exclude_elements)} Elemente (nav/header/footer)")

        return {
            'main_content_element': main_content_element,
            'exclude_elements': exclude_elements,
            'scored_elements': scored_elements[:5]  # Top 5 for reference
        }

    def filter_markdown_by_analysis(self, markdown: str, html: str, analysis: dict) -> str:
        """Filter markdown content based on HTML analysis to keep only main content."""
        print("🎯 Filtere Markdown basierend auf HTML-Analyse...")

        soup = BeautifulSoup(html, 'html.parser')
        main_element = analysis['main_content_element']
        exclude_elements = analysis['exclude_elements']

        if not main_element:
            print("   ⚠️  Kein spezifisches Main-Element gefunden, nutze komplettes Markdown")
            return markdown

        # Remove excluded elements from soup
        for elem in exclude_elements:
            elem.decompose()

        # Extract text from main content element only
        main_text = main_element.get_text(separator='\n', strip=True)

        # Split both into lines for comparison
        markdown_lines = markdown.split('\n')
        main_text_lines = [line.strip() for line in main_text.split('\n') if line.strip()]

        # Create a set of main content text fragments for fast lookup
        main_content_fragments = set()
        for line in main_text_lines:
            if len(line) > 10:  # Only consider substantial lines
                # Store first 50 chars as fragment identifier
                fragment = line[:50].lower()
                main_content_fragments.add(fragment)

        # Filter markdown lines: keep only those that appear in main content
        filtered_lines = []
        for line in markdown_lines:
            line_stripped = line.strip()

            # Always keep markdown structural elements
            if not line_stripped:
                filtered_lines.append(line)
                continue

            if line_stripped.startswith('#'):  # Headers
                filtered_lines.append(line)
                continue

            if line_stripped.startswith('|'):  # Tables
                filtered_lines.append(line)
                continue

            if line_stripped.startswith('- ') or line_stripped.startswith('* '):  # Lists
                # Check if list content is in main content
                list_text = line_stripped[2:].strip()[:50].lower()
                if any(list_text in fragment or fragment.startswith(list_text[:20])
                       for fragment in main_content_fragments):
                    filtered_lines.append(line)
                continue

            # For regular text lines, check if content appears in main element
            if len(line_stripped) > 10:
                line_fragment = line_stripped[:50].lower()
                if any(line_fragment in fragment or fragment.startswith(line_fragment[:20])
                       for fragment in main_content_fragments):
                    filtered_lines.append(line)
            else:
                # Keep short lines if previous line was kept
                if filtered_lines and filtered_lines[-1].strip():
                    filtered_lines.append(line)

        filtered_markdown = '\n'.join(filtered_lines)

        # Calculate reduction
        original_length = len(markdown)
        filtered_length = len(filtered_markdown)
        reduction_pct = ((original_length - filtered_length) / original_length * 100) if original_length > 0 else 0

        print(f"   ✓ Markdown gefiltert: {original_length} → {filtered_length} Zeichen ({reduction_pct:.1f}% Reduktion)")

        return filtered_markdown

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

        # Fix table headers: Remove lines that are just "---|---" which indicate
        # a markdown table header separator when the table shouldn't have a header
        # This happens with chronological tables where the first row is data, not headers
        cleaned = re.sub(r'\n---\|---\s*\n', '\n', cleaned)

        return cleaned.strip()

    def _create_frontmatter(self, markdown: str, metadata: dict, html: str = "") -> str:
        """Create YAML frontmatter."""
        timestamp = datetime.now().isoformat()
        content_hash = hashlib.sha256(markdown.encode()).hexdigest()

        title = metadata.get('title', 'Untitled')

        # Try AI-generated metadata first
        ai_metadata = self._generate_metadata_with_ai(markdown)

        if ai_metadata:
            description = ai_metadata.get('description', '')
            keywords = ai_metadata.get('keywords', [])
        else:
            # Fallback to heuristic methods
            description = self._generate_description(markdown)
            keywords = self._extract_keywords(markdown, title)

        # Detect language from HTML lang attribute
        language = self._detect_language_from_html(html)

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

    def _detect_language_from_html(self, html: str) -> str:
        """Detect language from HTML lang attribute."""
        if not html:
            return "en"

        try:
            # Use BeautifulSoup to parse HTML properly
            soup = BeautifulSoup(html, 'html.parser')

            # Try to get lang from <html> tag
            html_tag = soup.find('html')
            if html_tag and html_tag.get('lang'):
                lang = html_tag.get('lang').lower()
                # Return primary language code (e.g., 'de' from 'de-DE')
                return lang.split('-')[0]

            # Fallback: check og:locale meta tag
            og_locale = soup.find('meta', attrs={'name': 'og:locale'})
            if og_locale and og_locale.get('content'):
                lang = og_locale.get('content').lower()
                return lang.split('_')[0]

            # Fallback: check lang meta tag
            lang_meta = soup.find('meta', attrs={'name': 'language'})
            if lang_meta and lang_meta.get('content'):
                return lang_meta.get('content').lower().split('-')[0]

        except Exception as e:
            # If parsing fails, use regex fallback
            html_tag_match = re.search(r'<html[^>]+lang=["\']([a-zA-Z-]+)["\']', html, re.IGNORECASE)
            if html_tag_match:
                return html_tag_match.group(1).lower().split('-')[0]

        return "en"

    def _generate_metadata_with_ai(self, markdown: str) -> dict:
        """Generate description and keywords using AI."""
        # Check if API key is available
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("   ⚠️  ANTHROPIC_API_KEY nicht gefunden, nutze Fallback-Methoden")
            return None

        try:
            import anthropic

            # Truncate content if too long (max ~3000 tokens for input)
            content_preview = markdown[:8000] if len(markdown) > 8000 else markdown

            client = anthropic.Anthropic(api_key=api_key)

            message = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": f"""Analysiere diesen Website-Content und generiere:
1. Eine prägnante Beschreibung (1-2 Sätze, max 200 Zeichen) die den Hauptinhalt zusammenfasst
2. Die 10 wichtigsten Keywords (als Array)

Antworte NUR mit einem JSON-Objekt in diesem Format:
{{"description": "...", "keywords": ["...", "..."]}}

Content:
{content_preview}"""
                }]
            )

            # Parse JSON response
            response_text = message.content[0].text.strip()
            # Remove markdown code blocks if present
            response_text = re.sub(r'^```json\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)

            result = json.loads(response_text)
            print("   ✨ KI-generierte Metadaten erstellt")
            return result

        except ImportError:
            print("   ⚠️  anthropic library nicht installiert, nutze Fallback")
            return None
        except Exception as e:
            print(f"   ⚠️  KI-Generierung fehlgeschlagen: {e}, nutze Fallback")
            return None

    def _generate_description(self, markdown: str) -> str:
        """Generate description from markdown content."""
        # Remove headers
        text = re.sub(r'^#+\s+', '', markdown, flags=re.MULTILINE)

        # Remove markdown links but keep the text: [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # Remove remaining markdown formatting
        text = re.sub(r'[*_`]', '', text)

        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)

        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)

        # Find first substantial paragraph
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # Skip lines that are too short or look like navigation/links
        skip_patterns = [
            r'^mehr\s*\.{0,3}\s*$',  # Just "Mehr..."
            r'^\d+\s*$',              # Just numbers
            r'^weiter$',              # Just "Weiter"
            r'^zurück$',              # Just "Zurück"
        ]

        for line in lines:
            # Skip lines matching skip patterns
            if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
                continue

            # Skip lines that end with navigation markers
            if line.endswith('»') or line.endswith('...'):
                continue

            # Skip lines that are mostly navigation/links (contain lots of » or similar)
            nav_char_count = line.count('»') + line.count('›')
            if nav_char_count > 2:
                continue

            # Look for substantial content with letters (not just numbers/symbols)
            letter_count = len(re.findall(r'[a-zA-ZäöüßÄÖÜ]', line))
            if letter_count >= 40 and len(line) >= 50:
                if len(line) <= 200:
                    return line
                else:
                    truncated = line[:197]
                    last_space = truncated.rfind(' ')
                    if last_space > 0:
                        return truncated[:last_space] + '...'
                    return truncated + '...'

        # Fallback: combine lines until we have enough
        combined = []
        char_count = 0
        for line in lines:
            if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
                continue
            combined.append(line)
            char_count += len(line)
            if char_count >= 100:
                break

        clean_text = ' '.join(combined)
        if len(clean_text) <= 200:
            return clean_text if clean_text else "No description available"
        else:
            truncated = clean_text[:197]
            last_space = truncated.rfind(' ')
            if last_space > 0:
                return truncated[:last_space] + '...'
            return truncated + '...'

    def _extract_keywords(self, content: str, title: str) -> list:
        """Extract keywords from content."""
        text = f"{title} {content}".lower()

        # Remove markdown and special characters
        text = re.sub(r'[#*`\[\]()]', ' ', text)

        # Remove URLs
        text = re.sub(r'https?://\S+', ' ', text)

        # Remove email addresses
        text = re.sub(r'\S+@\S+', ' ', text)

        # Extract words (4+ letters)
        words = re.findall(r'\b[a-zäöüß]{4,}\b', text)

        # Filter out common technical/generic terms
        stopwords = {
            'http', 'https', 'html', 'href', 'link', 'site', 'page',
            'mehr', 'weiter', 'zurück', 'next', 'prev', 'navigation',
            'menu', 'header', 'footer', 'mail', 'email', 'info',
            'alle', 'dieser', 'diese', 'dieses', 'haben', 'wird',
            'sind', 'sein', 'auch', 'sich', 'nach', 'oder', 'kann',
            'über', 'beim', 'muss', 'etwa', 'dass', 'noch', 'hier',
            'dann', 'ihnen', 'seine', 'ihre', 'ihrer', 'einen', 'einem',
            'einer', 'werden', 'wurde', 'wurden', 'worden', 'damit',
            'nodeID', 'params', 'index', 'detail', 'cached', 'resource'
        }

        word_freq = defaultdict(int)
        for word in words:
            # Skip stopwords and words that look like URL fragments
            if word in stopwords:
                continue
            if word.startswith('http') or word.startswith('www'):
                continue
            if len(word) < 4:  # Skip very short words
                continue

            word_freq[word] += 1

        # Sort by frequency and take top keywords
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

        # Return top 10, but skip if frequency is too low (likely noise)
        keywords = []
        for word, freq in sorted_words[:15]:  # Check top 15
            if freq >= 2 or len(keywords) < 3:  # Include if appears 2+ times or we have less than 3 keywords
                keywords.append(word)
            if len(keywords) >= 10:
                break

        return keywords

    async def crawl(self):
        """Execute the smart crawl process with single-pass extraction."""
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

        print(f"🚀 Smart Crawl startet: {self.url}\n")

        # Check API key and inform user
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            print("✨ KI-Metadaten-Generierung aktiviert (Claude Haiku)")
        else:
            print("ℹ️  KI-Metadaten-Generierung nicht verfügbar")
            print("   → ANTHROPIC_API_KEY nicht gesetzt")
            print("   → Nutze heuristische Fallback-Methoden")
            print("   → Für bessere Metadaten: export ANTHROPIC_API_KEY=sk-ant-...")
        print()

        # Single-Pass: Crawl once and get both HTML and Markdown
        print("📊 Stufe 1: Seite laden (Single-Pass)")
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

            full_html = result.html
            full_markdown = result.markdown
            metadata = result.metadata or {}

        # Stage 2: Analyze HTML structure locally (no additional crawl!)
        print("\n🔍 Stufe 2: HTML-Analyse (lokal, kein erneutes Crawlen)")
        analysis = self.analyze_html_structure(full_html)

        # Stage 3: Filter markdown based on analysis
        print("\n🎯 Stufe 3: Markdown-Filterung")
        filtered_markdown = self.filter_markdown_by_analysis(full_markdown, full_html, analysis)

        # Stage 4: Clean markdown
        print("\n🧹 Stufe 4: Nachbearbeitung")
        cleaned_markdown = self.clean_markdown(filtered_markdown)

        # Create frontmatter
        frontmatter = self._create_frontmatter(cleaned_markdown, metadata, full_html)

        # Combine and save
        final_content = frontmatter + '\n\n' + cleaned_markdown

        # Save to file
        os.makedirs(self.output_dir, exist_ok=True)
        output_file = os.path.join(self.output_dir, 'index.md')

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_content)

        print(f"\n✅ Gespeichert: {output_file}")
        print(f"   📊 Token-Schätzung: {int(len(cleaned_markdown.split()) * 1.3)}")
        print(f"   📏 Zeichen: {len(cleaned_markdown)}")


async def main():
    parser = argparse.ArgumentParser(description='Smart website crawler with intelligent content extraction')
    parser.add_argument('url', help='URL to crawl')
    parser.add_argument('--output-dir', default='crawled_site', help='Output directory (default: crawled_site)')
    parser.add_argument('--wait-time', type=float, default=5.0, help='JavaScript wait time in seconds (default: 5.0)')
    parser.add_argument('--single-page', action='store_true', help='Only crawl the given URL (compatibility flag, always true for now)')

    # Asset management flags
    parser.add_argument('--download-assets', action='store_true', help='Download all images and files from the page')
    parser.add_argument('--interactive', action='store_true', help='Ask user for missing alt texts (requires --download-assets)')
    parser.add_argument('--generate-alt-texts', action='store_true', help='Auto-generate missing alt texts with AI (requires --download-assets)')

    # Quality control flag
    parser.add_argument('--quality-check', action='store_true', help='Run AI quality check at the end')

    args = parser.parse_args()

    crawler = SmartCrawler(
        url=args.url,
        output_dir=args.output_dir,
        wait_time=args.wait_time,
        download_assets=args.download_assets,
        interactive=args.interactive,
        generate_alt_texts=args.generate_alt_texts,
        quality_check=args.quality_check
    )

    await crawler.crawl()


if __name__ == '__main__':
    asyncio.run(main())
