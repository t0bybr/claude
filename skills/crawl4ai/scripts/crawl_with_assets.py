#!/usr/bin/env python3
"""
Advanced website crawler with asset download and structured metadata.

Features:
- Downloads all images and files
- Generates structured metadata (metadata.json, assets.json)
- Creates content.md with asset references
- Optional: AI-generated alt texts for images
- Optional: Quality check at the end
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
from typing import List, Dict, Optional


class SmartCrawlerWithAssets:
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

        # Asset tracking
        self.assets = {
            'images': [],
            'files': []
        }

        # Create output directories
        self.assets_dir = Path(output_dir) / "assets"
        self.images_dir = self.assets_dir / "images"
        self.files_dir = self.assets_dir / "files"

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

            if any(keyword in tag_id or keyword in tag_class for keyword in
                   ['content', 'main', 'article', 'inhalt', 'body', 'post']):
                content_candidates.append(tag)

        # Strategy 3: Find elements with high text-to-link ratio
        scored_elements = []
        for candidate in content_candidates if content_candidates else soup.find_all(['div', 'section', 'article']):
            text = candidate.get_text(strip=True)
            links = candidate.find_all('a')

            if len(text) > 200:
                text_length = len(text)
                link_text_length = sum(len(link.get_text(strip=True)) for link in links)
                link_count = len(links)

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
            'exclude_selectors': exclude_selectors[:10],
            'scored_elements': scored_elements[:5]
        }

    async def discover_assets(self, html: str) -> Dict[str, List[Dict]]:
        """Discover all images and files in the HTML (only from content area)."""
        print("🔍 Entdecke Assets (Bilder und Dateien im Content-Bereich)...")
        soup = BeautifulSoup(html, 'html.parser')

        discovered = {
            'images': [],
            'files': []
        }

        # Find all images
        for img in soup.find_all('img'):
            src = img.get('src')
            srcset = img.get('srcset')
            alt = img.get('alt', '')

            # Parse srcset for highest resolution
            best_src = self._parse_srcset(srcset) if srcset else src

            if best_src:
                # Convert relative to absolute URL
                absolute_url = urljoin(self.url, best_src)

                # Filter out icons and UI elements
                url_lower = absolute_url.lower()
                skip_patterns = ['icon', 'logo', 'menu', 'nav', 'button', 'arrow', 'sprite', 'header', 'footer']
                if any(pattern in url_lower for pattern in skip_patterns):
                    continue

                discovered['images'].append({
                    'url': absolute_url,
                    'alt_text': alt,
                    'alt_missing': not bool(alt),
                    'tag': str(img)
                })

        # Find all file links (PDF, DOC, ZIP, etc.)
        file_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rar', '.txt']
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if any(href.lower().endswith(ext) for ext in file_extensions):
                absolute_url = urljoin(self.url, href)
                link_text = link.get_text(strip=True)

                discovered['files'].append({
                    'url': absolute_url,
                    'link_text': link_text,
                    'tag': str(link)
                })

        print(f"   ✓ {len(discovered['images'])} Bilder gefunden (Icons/UI-Elemente gefiltert)")
        print(f"   ✓ {len(discovered['files'])} Dateien gefunden")

        return discovered

    def _parse_srcset(self, srcset: str) -> Optional[str]:
        """Parse srcset and return the highest resolution image URL."""
        if not srcset:
            return None

        # srcset format: "url 1x, url 2x" or "url 100w, url 200w"
        candidates = []
        for item in srcset.split(','):
            parts = item.strip().split()
            if len(parts) >= 2:
                url = parts[0]
                descriptor = parts[1]

                # Extract numeric value
                if descriptor.endswith('w'):
                    width = int(descriptor[:-1])
                    candidates.append((width, url))
                elif descriptor.endswith('x'):
                    multiplier = float(descriptor[:-1])
                    candidates.append((multiplier * 1000, url))  # Treat as pseudo-width

        if candidates:
            # Return URL with highest width/multiplier
            candidates.sort(reverse=True)
            return candidates[0][1]

        return None

    async def download_asset(self, url: str, asset_type: str) -> Optional[Dict]:
        """Download a single asset and return metadata."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        print(f"   ⚠️  Fehler beim Download: {url} (Status: {response.status})")
                        return None

                    content = await response.read()
                    content_type = response.headers.get('Content-Type', 'application/octet-stream')

                    # Generate hash
                    file_hash = hashlib.sha256(content).hexdigest()[:16]  # Use first 16 chars

                    # Determine file extension
                    if asset_type == 'image':
                        ext = self._get_image_extension(content_type)
                        filename = f"{file_hash}{ext}"
                        save_dir = self.images_dir
                    else:  # file
                        ext = self._get_file_extension(url, content_type)
                        filename = f"{file_hash}{ext}"
                        save_dir = self.files_dir

                    # Save file
                    save_dir.mkdir(parents=True, exist_ok=True)
                    file_path = save_dir / filename

                    with open(file_path, 'wb') as f:
                        f.write(content)

                    # Get image dimensions if it's an image
                    width, height = None, None
                    if asset_type == 'image':
                        try:
                            from PIL import Image
                            import io
                            img = Image.open(io.BytesIO(content))
                            width, height = img.size
                        except:
                            pass

                    metadata = {
                        'hash': file_hash,
                        'filename': filename,
                        'original_url': url,
                        'size': len(content),
                        'mime_type': content_type,
                        'downloaded_at': datetime.now().isoformat(),
                    }

                    # Add image-specific metadata
                    if asset_type == 'image':
                        metadata['width'] = width
                        metadata['height'] = height

                    # Save metadata as separate JSON file
                    json_path = save_dir / f"{file_hash}.json"
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)

                    return metadata

        except asyncio.TimeoutError:
            print(f"   ⏱️  Timeout beim Download: {url}")
            return None
        except Exception as e:
            print(f"   ❌ Fehler beim Download von {url}: {e}")
            return None

    def _get_image_extension(self, content_type: str) -> str:
        """Get image file extension from content type."""
        extensions = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'image/svg+xml': '.svg'
        }
        return extensions.get(content_type, '.jpg')

    def _get_file_extension(self, url: str, content_type: str) -> str:
        """Get file extension from URL or content type."""
        # Try to get from URL first
        parsed = urlparse(url)
        path = parsed.path
        if '.' in path:
            return path[path.rfind('.'):]

        # Fallback to content type
        extensions = {
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/zip': '.zip',
            'text/plain': '.txt'
        }
        return extensions.get(content_type, '.bin')

    async def download_all_assets(self, discovered: Dict) -> None:
        """Download all discovered assets."""
        if not self.download_assets:
            return

        print("\n📥 Lade Assets herunter...")

        # Download images
        if discovered['images']:
            print(f"\n   Lade {len(discovered['images'])} Bilder...")
            for i, img_info in enumerate(discovered['images'], 1):
                print(f"   [{i}/{len(discovered['images'])}] {img_info['url']}")
                metadata = await self.download_asset(img_info['url'], 'image')

                if metadata:
                    metadata['alt_text'] = img_info['alt_text']
                    metadata['alt_text_missing'] = img_info['alt_missing']
                    metadata['alt_text_generated'] = False
                    self.assets['images'].append(metadata)

        # Download files
        if discovered['files']:
            print(f"\n   Lade {len(discovered['files'])} Dateien...")
            for i, file_info in enumerate(discovered['files'], 1):
                print(f"   [{i}/{len(discovered['files'])}] {file_info['url']}")
                metadata = await self.download_asset(file_info['url'], 'file')

                if metadata:
                    metadata['link_text'] = file_info['link_text']
                    self.assets['files'].append(metadata)

        print(f"\n   ✅ {len(self.assets['images'])} Bilder heruntergeladen")
        print(f"   ✅ {len(self.assets['files'])} Dateien heruntergeladen")

    async def handle_alt_texts(self) -> None:
        """Handle missing alt texts (interactive or AI-generated)."""
        if not self.download_assets:
            return

        missing_alts = [img for img in self.assets['images'] if img['alt_text_missing']]

        if not missing_alts:
            print("\n   ✓ Alle Bilder haben Alt-Texte")
            return

        print(f"\n⚠️  {len(missing_alts)} Bilder haben keine Alt-Texte")

        if self.interactive:
            await self._interactive_alt_texts(missing_alts)
        elif self.generate_alt_texts:
            await self._generate_alt_texts_ai(missing_alts)
        else:
            print("   → Nutze --interactive oder --generate-alt-texts zum Hinzufügen")

    async def _interactive_alt_texts(self, images: List[Dict]) -> None:
        """Ask user for alt texts interactively."""
        print("\n📝 Interaktiver Alt-Text Modus")
        print("   Bitte gib Alt-Texte für Bilder ohne Alt-Text ein:")
        print("   (Leer lassen um zu überspringen)\n")

        for img in images:
            print(f"   Bild: {img['filename']}")
            print(f"   URL: {img['original_url']}")
            print(f"   Größe: {img['width']}x{img['height']}px" if img['width'] else "")

            alt_text = input("   Alt-Text: ").strip()

            if alt_text:
                img['alt_text'] = alt_text
                img['alt_text_missing'] = False
                img['alt_text_generated'] = False

                # Update JSON file
                json_path = self.images_dir / f"{img['hash']}.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(img, f, indent=2, ensure_ascii=False)

                print("   ✓ Alt-Text gespeichert\n")
            else:
                print("   → Übersprungen\n")

    async def _generate_alt_texts_ai(self, images: List[Dict]) -> None:
        """Generate alt texts using AI."""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("   ⚠️  ANTHROPIC_API_KEY nicht gefunden")
            print("   → Kann keine Alt-Texte generieren")
            return

        print("\n✨ Generiere Alt-Texte mit KI...")

        try:
            import anthropic
            import base64

            client = anthropic.Anthropic(api_key=api_key)

            for i, img in enumerate(images, 1):
                print(f"   [{i}/{len(images)}] {img['filename']}")

                # Read image file
                img_path = self.images_dir / img['filename']
                with open(img_path, 'rb') as f:
                    image_data = base64.standard_b64encode(f.read()).decode('utf-8')

                # Determine media type
                media_type = img['mime_type']

                try:
                    message = client.messages.create(
                        model="claude-3-haiku-20240307",
                        max_tokens=100,
                        messages=[{
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": image_data
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": "Beschreibe dieses Bild in 1-2 kurzen Sätzen für einen Alt-Text. Sei präzise und beschreibend."
                                }
                            ]
                        }]
                    )

                    alt_text = message.content[0].text.strip()
                    img['alt_text'] = alt_text
                    img['alt_text_missing'] = False
                    img['alt_text_generated'] = True

                    # Update JSON file
                    json_path = self.images_dir / f"{img['hash']}.json"
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(img, f, indent=2, ensure_ascii=False)

                    print(f"      ✓ \"{alt_text}\"")

                except Exception as e:
                    print(f"      ⚠️  Fehler: {e}")

        except ImportError:
            print("   ⚠️  anthropic library nicht installiert")

    def replace_asset_urls_in_markdown(self, markdown: str) -> str:
        """Replace asset URLs in markdown with references."""
        if not self.download_assets:
            return markdown

        print("\n🔄 Ersetze Asset-URLs mit Referenzen...")

        # Replace image URLs
        for img in self.assets['images']:
            # Find image references in markdown
            url = img['original_url']
            alt = img.get('alt_text', '')
            hash_ref = img['hash']

            # Pattern: ![alt](url) or <img src="url">
            markdown = re.sub(
                rf'!\[([^\]]*)\]\({re.escape(url)}\)',
                f'[IMAGE: {hash_ref} | Alt: "{alt}"]',
                markdown
            )

        # Replace file URLs
        for file in self.assets['files']:
            url = file['original_url']
            hash_ref = file['hash']
            filename = Path(url).name
            size_kb = file['size'] // 1024

            # Pattern: [text](url)
            markdown = re.sub(
                rf'\[([^\]]+)\]\({re.escape(url)}\)',
                f'[FILE: {hash_ref} | {filename} | {size_kb} KB]',
                markdown
            )

        return markdown

    async def quality_check_ai(self, markdown: str, metadata: dict) -> None:
        """Run AI quality check on the crawled content."""
        if not self.quality_check:
            return

        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("\n⚠️  Qualitätskontrolle übersprungen (kein API-Key)")
            return

        print("\n🔍 Qualitätskontrolle läuft...")

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)

            # Truncate content for analysis
            content_preview = markdown[:5000] if len(markdown) > 5000 else markdown

            message = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": f"""Prüfe diesen gecrawlten Website-Content auf Qualität:

Markdown Content:
{content_preview}

Metadaten:
{json.dumps(metadata, indent=2)}

Prüfe:
1. Ist die Markdown-Formatierung korrekt?
2. Sind die Referenzen [IMAGE: ...] und [FILE: ...] sinnvoll platziert?
3. Fehlt wichtiger Content?
4. Sind Duplikate vorhanden?
5. Ist die Description/Keywords passend?

Gib einen kurzen Bericht mit Problemen und Empfehlungen."""
                }]
            )

            report = message.content[0].text.strip()

            print("\n📋 Qualitätsbericht:")
            print("─" * 60)
            print(report)
            print("─" * 60)

        except Exception as e:
            print(f"\n❌ Qualitätskontrolle fehlgeschlagen: {e}")

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

    async def crawl_with_selector(self, selector: str, exclude_tags: list) -> dict:
        """Crawl page using specific CSS selector."""
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

        print(f"📥 Lade Seite mit Selektor: {selector}")

        browser_config = BrowserConfig(
            headless=True,
            verbose=False
        )

        excluded_selector = ', '.join(exclude_tags) if exclude_tags else None

        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=60000,
            css_selector=selector,
            excluded_selector=excluded_selector,
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

    async def crawl(self):
        """Execute the complete crawl process with asset download."""
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

        print(f"🚀 Advanced Crawl startet: {self.url}\n")

        # Show flags status
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            print("✨ KI-Features aktiviert (Claude Haiku)")
        else:
            print("ℹ️  KI-Features nicht verfügbar (kein ANTHROPIC_API_KEY)")

        if self.download_assets:
            print("📥 Asset-Download aktiviert")
            if self.interactive:
                print("   → Interaktiver Alt-Text Modus")
            if self.generate_alt_texts:
                print("   → KI-generierte Alt-Texte")

        if self.quality_check:
            print("🔍 Qualitätskontrolle aktiviert")

        print()

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

            full_html = result.html
            analysis = await self.analyze_html_structure(result.html)

        # Stage 2: Extract content with selector
        print("\n📝 Stufe 2: Inhalts-Extraktion")
        content_result = await self.crawl_with_selector(
            analysis['content_selector'],
            analysis['exclude_selectors']
        )

        # Stage 3: Discover assets (only from extracted content)
        if self.download_assets:
            discovered = await self.discover_assets(content_result['html'])
        else:
            discovered = {'images': [], 'files': []}

        # Stage 4: Download assets
        await self.download_all_assets(discovered)

        # Stage 5: Handle alt texts
        await self.handle_alt_texts()

        # Stage 6: Clean and process markdown
        print("\n✨ Stufe 3: Nachbearbeitung")
        cleaned_markdown = self.clean_markdown(content_result['markdown'])

        # Replace URLs with asset references
        final_markdown = self.replace_asset_urls_in_markdown(cleaned_markdown)

        # Stage 7: Generate metadata
        print("\n📊 Generiere Metadaten...")

        title = content_result['metadata'].get('title', 'Untitled')

        # Try AI-generated metadata first
        ai_metadata = self._generate_metadata_with_ai(final_markdown)

        if ai_metadata:
            description = ai_metadata.get('description', '')
            keywords = ai_metadata.get('keywords', [])
        else:
            # Fallback to heuristic methods
            print("   ℹ️  Nutze heuristische Fallback-Methoden")
            description = self._generate_description(final_markdown)
            keywords = self._extract_keywords(final_markdown, title)

        # Detect language from HTML
        language = self._detect_language_from_html(full_html)

        # Collect asset hashes for metadata
        image_hashes = [img['hash'] for img in self.assets['images']]
        file_hashes = [file['hash'] for file in self.assets['files']]

        metadata = {
            'crawled_at': datetime.now().isoformat(),
            'url': self.url,
            'title': title,
            'content_hash': hashlib.sha256(final_markdown.encode()).hexdigest(),
            'language': language,
            'estimated_tokens': int(len(final_markdown.split()) * 1.3),
            'description': description,
            'keywords': keywords[:10],  # Limit to top 10
            'image_hashes': image_hashes,
            'file_hashes': file_hashes
        }

        # Stage 8: Save everything
        print("\n💾 Speichere Dateien...")
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save metadata.json
        with open(output_path / 'metadata.json', 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"   ✓ metadata.json")

        # Info about assets (individual JSON files already saved)
        if self.download_assets:
            print(f"   ✓ {len(image_hashes)} Bild-JSONs in assets/images/")
            print(f"   ✓ {len(file_hashes)} Datei-JSONs in assets/files/")

        # Save content.md
        with open(output_path / 'content.md', 'w', encoding='utf-8') as f:
            f.write(final_markdown)
        print(f"   ✓ content.md")

        # Stage 9: Quality check
        await self.quality_check_ai(final_markdown, metadata)

        print(f"\n✅ Fertig! Ausgabe in: {output_path}")


async def main():
    parser = argparse.ArgumentParser(description='Advanced website crawler with asset download')
    parser.add_argument('url', help='URL to crawl')
    parser.add_argument('--output-dir', default='crawled_site', help='Output directory (default: crawled_site)')
    parser.add_argument('--wait-time', type=float, default=5.0, help='JavaScript wait time in seconds (default: 5.0)')

    # Asset management flags
    parser.add_argument('--download-assets', action='store_true', help='Download all images and files from the page')
    parser.add_argument('--interactive', action='store_true', help='Ask user for missing alt texts (requires --download-assets)')
    parser.add_argument('--generate-alt-texts', action='store_true', help='Auto-generate missing alt texts with AI (requires --download-assets)')

    # Quality control flag
    parser.add_argument('--quality-check', action='store_true', help='Run AI quality check at the end')

    args = parser.parse_args()

    crawler = SmartCrawlerWithAssets(
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
