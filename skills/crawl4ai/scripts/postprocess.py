#!/usr/bin/env python3
"""
Phase 2: Post-Processing

Takes bulk-crawled raw data and:
1. Cleans markdown content
2. Generates/enriches metadata (AI or heuristic)
3. Creates final content.md + metadata.json for each page
"""

import asyncio
import argparse
import json
import os
import re
import hashlib
import base64
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from bs4 import BeautifulSoup


class PostProcessor:
    def __init__(self, crawled_dir: str, use_ai: bool = True, batch_size: int = 10,
                 generate_alt_texts: bool = False):
        self.crawled_dir = Path(crawled_dir)
        self.use_ai = use_ai
        self.batch_size = batch_size
        self.generate_alt_texts = generate_alt_texts

    def find_page_dirs(self) -> list:
        """Find all page directories with raw.md files."""
        page_dirs = []

        for item in self.crawled_dir.iterdir():
            if item.is_dir() and (item / 'raw.md').exists():
                page_dirs.append(item)

        return page_dirs

    def clean_markdown(self, markdown: str) -> str:
        """Clean markdown content (same logic as old version)."""
        lines = markdown.split('\n')
        cleaned_lines = []
        prev_line = ""

        skip_patterns = [
            r'^\s*\[.*menu.*\].*$',
            r'^\s*\[.*nav.*\].*$',
            r'^\s*open submenu',
            r'^\s*close submenu',
            r'^\s*\+\s*$',
            r'^\s*-\s*$',
            r'^\s*×\s*$',
            r'^\s*zoom',
            r'^\s*\[prev\]',
            r'^\s*\[next\]',
            r'^\s*\[start\]',
            r'^\s*\[stop\]',
            r'^\s*slider',
            r'gehe zum',
            r'zur startseite',
            r'^\s*\[zur.{0,2}ck\]',
            r'^\s*\[weiter\]',
            r'^\s*\[\d+\]\(',
            r'^\s*\d+\|',
            r'^\s*\[alle .*aufrufen',
        ]

        seen_chunks = set()

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

            # Check for duplicate sections
            if i + 5 < len(lines):
                chunk = ''.join(lines[i:i+5]).strip()
                if chunk in seen_chunks and len(chunk) > 50:
                    continue
                if len(chunk) > 50:
                    seen_chunks.add(chunk)

            cleaned_lines.append(line)
            prev_line = line

        # Remove excessive whitespace
        cleaned = '\n'.join(cleaned_lines)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        # Fix table headers
        cleaned = re.sub(r'\n---\|---\s*\n', '\n', cleaned)

        return cleaned.strip()

    def detect_language_from_html(self, html_path: Path) -> str:
        """Detect language from HTML file."""
        if not html_path.exists():
            return "en"

        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html = f.read()

            soup = BeautifulSoup(html, 'html.parser')

            # Try to get lang from <html> tag
            html_tag = soup.find('html')
            if html_tag and html_tag.get('lang'):
                lang = html_tag.get('lang').lower()
                return lang.split('-')[0]

            # Fallback: check og:locale meta tag
            og_locale = soup.find('meta', attrs={'property': 'og:locale'})
            if og_locale and og_locale.get('content'):
                lang = og_locale.get('content').lower()
                return lang.split('_')[0]

        except Exception as e:
            pass

        return "en"

    def generate_description_heuristic(self, markdown: str) -> str:
        """Generate description using heuristic methods."""
        # Remove headers
        text = re.sub(r'^#+\s+', '', markdown, flags=re.MULTILINE)

        # Remove markdown links but keep text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # Remove remaining markdown formatting
        text = re.sub(r'[*_`]', '', text)

        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)

        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)

        # Find first substantial paragraph
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        skip_patterns = [
            r'^mehr\s*\.{0,3}\s*$',
            r'^\d+\s*$',
            r'^weiter$',
            r'^zurück$',
        ]

        for line in lines:
            if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
                continue

            if line.endswith('»') or line.endswith('...'):
                continue

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

        return "No description available"

    def is_alt_text_generic(self, alt_text: str) -> bool:
        """Check if alt text is generic or unhelpful."""
        if not alt_text or len(alt_text.strip()) == 0:
            return True

        alt_lower = alt_text.lower().strip()

        # Too short (less than 5 characters)
        if len(alt_lower) < 5:
            return True

        # Generic terms
        generic_terms = [
            'bild', 'image', 'foto', 'photo', 'picture', 'img',
            'icon', 'logo', 'banner', 'header', 'footer',
        ]

        if alt_lower in generic_terms:
            return True

        # Just a filename
        if re.match(r'^[a-z0-9_\-]+\.(jpg|png|gif|webp)$', alt_lower):
            return True

        # Very short names (likely just proper nouns without context)
        words = alt_lower.split()
        if len(words) <= 2 and len(alt_lower) < 20:
            # Might be generic like "Fürstlicher Park" (just a name)
            return True

        return False

    def generate_alt_text_with_ai(self, image_path: Path) -> str:
        """Generate alt text for image using Claude Vision API."""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return None

        try:
            import anthropic

            # Read and encode image
            with open(image_path, 'rb') as f:
                image_data = base64.standard_b64encode(f.read()).decode('utf-8')

            # Determine media type
            ext = image_path.suffix.lower()
            media_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            media_type = media_types.get(ext, 'image/jpeg')

            client = anthropic.Anthropic(api_key=api_key)

            message = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Beschreibe dieses Bild in 1-2 prägnanten Sätzen für einen Alt-Text. Fokussiere auf das Wesentliche und den Kontext. Antworte NUR mit der Beschreibung, ohne zusätzlichen Text."
                        }
                    ],
                }]
            )

            alt_text = message.content[0].text.strip()
            return alt_text

        except Exception as e:
            print(f"   ⚠️  Alt-Text-Generierung fehlgeschlagen: {e}")
            return None

    async def process_image_alt_texts(self, page_dir: Path):
        """Process and improve alt texts for images."""
        if not self.generate_alt_texts:
            return

        assets_dir = page_dir / 'assets' / 'images'
        if not assets_dir.exists():
            return

        # Find all image metadata files
        image_jsons = list(assets_dir.glob('*.json'))
        if not image_jsons:
            return

        print(f"   🖼️  Prüfe {len(image_jsons)} Bild-Alt-Texts...")

        improved_count = 0
        for json_file in image_jsons:
            with open(json_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            alt_text = metadata.get('alt_text', '')

            # Check if alt text needs improvement
            if self.is_alt_text_generic(alt_text):
                # Find corresponding image file
                hash_name = metadata['hash']
                filename = metadata['filename']
                image_file = assets_dir / filename

                if not image_file.exists():
                    continue

                print(f"      → Generiere Alt-Text für {filename}...")

                # Generate new alt text with AI
                new_alt_text = self.generate_alt_text_with_ai(image_file)

                if new_alt_text:
                    metadata['alt_text'] = new_alt_text
                    metadata['alt_text_generated'] = True
                    metadata['alt_text_original'] = alt_text

                    # Save updated metadata
                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)

                    improved_count += 1

        if improved_count > 0:
            print(f"   ✨ {improved_count} Alt-Texts verbessert")

    def extract_keywords_heuristic(self, content: str, title: str) -> list:
        """Extract keywords using heuristic methods."""
        text = f"{title} {content}".lower()

        # Remove markdown and special characters
        text = re.sub(r'[#*`\[\]()]', ' ', text)
        text = re.sub(r'https?://\S+', ' ', text)
        text = re.sub(r'\S+@\S+', ' ', text)

        # Extract words (4+ letters)
        words = re.findall(r'\b[a-zäöüß]{4,}\b', text)

        # Filter stopwords
        stopwords = {
            'http', 'https', 'html', 'href', 'link', 'site', 'page',
            'mehr', 'weiter', 'zurück', 'next', 'prev', 'navigation',
            'menu', 'header', 'footer', 'mail', 'email', 'info',
            'alle', 'dieser', 'diese', 'dieses', 'haben', 'wird',
            'sind', 'sein', 'auch', 'sich', 'nach', 'oder', 'kann',
            'über', 'beim', 'muss', 'etwa', 'dass', 'noch', 'hier',
            'dann', 'ihnen', 'seine', 'ihre', 'ihrer', 'einen', 'einem',
            'einer', 'werden', 'wurde', 'wurden', 'worden', 'damit',
        }

        word_freq = defaultdict(int)
        for word in words:
            if word not in stopwords and len(word) >= 4:
                word_freq[word] += 1

        # Sort by frequency
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

        keywords = []
        for word, freq in sorted_words[:15]:
            if freq >= 2 or len(keywords) < 3:
                keywords.append(word)
            if len(keywords) >= 10:
                break

        return keywords

    def generate_metadata_with_ai(self, markdown: str) -> dict:
        """Generate description and keywords using AI."""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return None

        try:
            import anthropic

            # Truncate content if too long
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
            response_text = re.sub(r'^```json\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)

            result = json.loads(response_text)
            return result

        except Exception as e:
            print(f"   ⚠️  AI generation failed: {e}")
            return None

    async def process_page(self, page_dir: Path):
        """Process a single page directory."""
        print(f"📄 Processing: {page_dir.name}")

        # Step 0: Improve alt texts if enabled
        await self.process_image_alt_texts(page_dir)

        # Read raw markdown
        raw_md_path = page_dir / 'raw.md'
        with open(raw_md_path, 'r', encoding='utf-8') as f:
            raw_markdown = f.read()

        # Read existing metadata
        metadata_path = page_dir / 'metadata.json'
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        # Step 1: Clean markdown
        cleaned_markdown = self.clean_markdown(raw_markdown)

        # Step 2: Generate/enrich metadata
        if self.use_ai:
            ai_metadata = self.generate_metadata_with_ai(cleaned_markdown)
            if ai_metadata:
                description = ai_metadata.get('description', '')
                keywords = ai_metadata.get('keywords', [])
                print(f"   ✨ AI metadata generated")
            else:
                description = self.generate_description_heuristic(cleaned_markdown)
                keywords = self.extract_keywords_heuristic(cleaned_markdown, metadata.get('title', ''))
                print(f"   📝 Heuristic metadata generated")
        else:
            description = self.generate_description_heuristic(cleaned_markdown)
            keywords = self.extract_keywords_heuristic(cleaned_markdown, metadata.get('title', ''))
            print(f"   📝 Heuristic metadata generated")

        # Step 3: Detect language
        html_path = page_dir / 'raw.html'
        language = self.detect_language_from_html(html_path)

        # Step 4: Calculate metrics
        content_hash = hashlib.sha256(cleaned_markdown.encode()).hexdigest()
        estimated_tokens = int(len(cleaned_markdown.split()) * 1.3)

        # Step 5: Enrich metadata (in correct order like reference!)
        enriched_metadata = {
            'crawled_at': metadata.get('crawled_at'),
            'url': metadata.get('url'),
            'title': metadata.get('title', 'Untitled'),
            'content_hash': content_hash,
            'language': language,
            'estimated_tokens': estimated_tokens,
            'description': description,
            'keywords': keywords[:10],
        }

        # Add asset hashes AFTER keywords (like in reference)
        if 'image_hashes' in metadata:
            enriched_metadata['image_hashes'] = metadata['image_hashes']
        else:
            enriched_metadata['image_hashes'] = []

        if 'file_hashes' in metadata:
            enriched_metadata['file_hashes'] = metadata['file_hashes']
        else:
            enriched_metadata['file_hashes'] = []

        metadata = enriched_metadata

        # Step 6: Save enriched metadata
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Step 7: Save cleaned content as content.md (NO frontmatter!)
        content_path = page_dir / 'content.md'
        with open(content_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_markdown)

        print(f"   ✓ Saved content.md + enriched metadata.json")
        print(f"   📊 {estimated_tokens} tokens, {len(cleaned_markdown)} chars")

    async def process_all(self):
        """Process all pages."""
        print(f"🚀 Post-Processing startet: {self.crawled_dir}\n")

        # Check API key
        if self.use_ai:
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if api_key:
                print("✨ AI metadata generation enabled (Claude Haiku)")
            else:
                print("⚠️  ANTHROPIC_API_KEY not set, using heuristic methods")
                self.use_ai = False

        print()

        # Find all page directories
        page_dirs = self.find_page_dirs()
        print(f"📂 Found {len(page_dirs)} pages to process\n")

        if not page_dirs:
            print("❌ No pages found with raw.md files")
            return

        # Process pages
        for page_dir in page_dirs:
            await self.process_page(page_dir)
            print()

        print(f"\n✅ Post-processing complete!")
        print(f"   📄 Processed: {len(page_dirs)} pages")


async def main():
    parser = argparse.ArgumentParser(
        description='Phase 2: Post-process bulk-crawled data'
    )
    parser.add_argument('crawled_dir', help='Directory with bulk-crawled data')
    parser.add_argument('--no-ai', action='store_true',
                       help='Disable AI metadata generation (use heuristic methods)')
    parser.add_argument('--generate-alt-texts', action='store_true',
                       help='Generate better alt texts for images with AI (requires ANTHROPIC_API_KEY)')

    args = parser.parse_args()

    processor = PostProcessor(
        crawled_dir=args.crawled_dir,
        use_ai=not args.no_ai,
        generate_alt_texts=args.generate_alt_texts
    )

    await processor.process_all()


if __name__ == '__main__':
    asyncio.run(main())
