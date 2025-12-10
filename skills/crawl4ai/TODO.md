# TODO: crawl_with_assets.py Implementation

## Status: VOLLSTÄNDIG FERTIG ✅
Das Script ist vollständig implementiert, getestet und funktionsfähig. Alle Features sind integriert.

## Ziel
Erweitertes Crawling-Script mit Asset-Download, strukturierten Metadaten und Qualitätskontrolle.

## Ausgabe-Struktur
```
crawled_site/
├── metadata.json          # Seitenmetadaten mit Hash-Referenzen
├── content.md             # Content mit [IMAGE: hash] und [FILE: hash] Referenzen
└── assets/
    ├── images/
    │   ├── abc123def456.json  # Metadaten für dieses Bild
    │   └── abc123def456.jpg   # Das Bild selbst
    └── files/
        ├── xyz789uvw012.json  # Metadaten für diese Datei
        └── xyz789uvw012.pdf   # Die Datei selbst
```

**Wichtig:** Jedes Asset hat seine eigene JSON-Datei mit Metadaten. metadata.json enthält nur Arrays mit Hashes (`image_hashes`, `file_hashes`).

## Features

### 1. Asset-Download System ✅
- [x] Download-Funktion für Bilder (async mit aiohttp)
- [x] srcset parsen für höchste Auflösung
- [x] Download-Funktion für Dateien (PDFs, DOCs, etc.)
- [x] SHA256-Hash-Generierung für alle Assets (erste 16 Zeichen)
- [x] Relative URLs zu absoluten URLs auflösen
- [x] Fehlerbehandlung (404, Timeout, etc.)
- [x] Progress-Anzeige beim Download
- [x] **NUR Content-Assets**: Nur Bilder/Dateien aus dem extrahierten `<main>` Bereich
- [x] **Icon-Filterung**: UI-Elemente (logo, icon, menu, nav) werden ausgeschlossen

### 2. Metadaten-Struktur ✅

**metadata.json:** (Hauptmetadaten mit Hash-Referenzen)
```json
{
  "crawled_at": "2025-11-04T...",
  "url": "https://example.com",
  "title": "Page Title",
  "language": "de",
  "content_hash": "abc123...",
  "estimated_tokens": 500,
  "description": "AI-generated description",
  "keywords": ["keyword1", "keyword2"],
  "image_hashes": ["abc123def456", "def789ghi012"],
  "file_hashes": ["xyz789uvw012"]
}
```

**assets/images/abc123def456.json:** (Pro Bild eine eigene JSON)
```json
{
  "hash": "abc123def456",
  "filename": "abc123def456.jpg",
  "original_url": "https://example.com/image.jpg",
  "size": 123456,
  "mime_type": "image/jpeg",
  "downloaded_at": "2025-11-04T...",
  "width": 1920,
  "height": 1080,
  "alt_text": "Description of image",
  "alt_text_generated": false,
  "alt_text_missing": false
}
```

**assets/files/xyz789uvw012.json:** (Pro Datei eine eigene JSON)
```json
{
  "hash": "xyz789uvw012",
  "filename": "xyz789uvw012.pdf",
  "original_url": "https://example.com/doc.pdf",
  "size": 234567,
  "mime_type": "application/pdf",
  "downloaded_at": "2025-11-04T..."
}
```

### 3. Markdown-Referenzen
Im content.md werden Assets referenziert:
```markdown
[IMAGE: abc123def456 | Alt: "Beautiful sunset"]

Download the document here: [FILE: xyz789uvw012 | document.pdf | 229 KB]
```

### 4. Alt-Text-Handling
- [ ] Erkennung fehlender Alt-Texte
- [ ] Flag `--interactive`: Frage User nach Alt-Text
- [ ] Flag `--generate-alt-texts`: KI generiert Alt-Texte (Claude Haiku + Vision)
- [ ] Markierung in assets.json ob generiert oder original

### 5. Qualitätskontrolle
- [ ] Flag `--quality-check`: KI-basierte Qualitätsprüfung am Ende
- [ ] Prüft: Markdown-Formatierung, Vollständigkeit, Bildverweise
- [ ] Gibt Bericht aus mit gefundenen Problemen
- [ ] Optional: Auto-Fix für einfache Probleme

### 6. CLI-Flags
```bash
python crawl_with_assets.py <url> [options]

Options:
  --output-dir DIR              Output directory (default: crawled_site)
  --wait-time SECONDS           JavaScript wait time (default: 5.0)

  Asset Management:
  --download-assets             Download all images and files
  --interactive                 Ask for missing alt texts (requires --download-assets)
  --generate-alt-texts          Auto-generate alt texts with AI (requires --download-assets)

  Quality Control:
  --quality-check               Run AI quality check at the end
```

## Implementierungsschritte

### ✅ VOLLSTÄNDIG IMPLEMENTIERT:

1. **Script-Grundstruktur** ✅
   - SmartCrawlerWithAssets Klasse erstellt
   - CLI-Flags hinzugefügt (--download-assets, --interactive, --generate-alt-texts, --quality-check)
   - 3-stufige Crawling-Logik integriert (HTML-Analyse → Inhalts-Extraktion → Nachbearbeitung)

2. **Asset-Download** ✅
   - discover_assets(): Findet Bilder und Dateien **NUR im Content-Bereich** (nicht im gesamten HTML)
   - Icon-Filterung: Schließt UI-Elemente aus (logo, icon, menu, nav, header, footer)
   - _parse_srcset(): Parst srcset für höchste Auflösung
   - download_asset(): Async Download mit aiohttp, 30s Timeout
   - Hash-Generierung (SHA256, erste 16 Zeichen)
   - Speicherung in assets/images/ und assets/files/
   - **Pro Asset eine eigene JSON-Datei** mit Metadaten
   - Bildgrößen-Extraktion mit Pillow

3. **Metadaten-System** ✅
   - metadata.json: Seiten-Metadaten mit `image_hashes` und `file_hashes` Arrays
   - assets/images/hash.json: Individuelle Bild-Metadaten
   - assets/files/hash.json: Individuelle Datei-Metadaten
   - content.md: Markdown mit [IMAGE: hash] und [FILE: hash] Referenzen
   - **Keine zentrale assets.json mehr**

4. **Alt-Text-Features** ✅
   - handle_alt_texts(): Erkennt fehlende Alt-Texte
   - _interactive_alt_texts(): Fragt User interaktiv, aktualisiert JSON
   - _generate_alt_texts_ai(): Nutzt Claude Vision API für Auto-Generierung
   - Markierung in Asset-JSON ob generiert oder original
   - JSON-Dateien werden automatisch aktualisiert

5. **Qualitätskontrolle** ✅
   - quality_check_ai(): KI prüft Markdown, Referenzen, Vollständigkeit
   - Gibt detaillierten Bericht aus

6. **Content-Cleaning** ✅
   - clean_markdown(): Entfernt Navigation, Pagination, Duplikate
   - Bereinigt Tabellen-Header
   - Entfernt excessive Whitespace
   - Alle Patterns aus crawl_to_markdown.py übernommen

7. **KI-Metadaten-Generierung** ✅
   - _generate_metadata_with_ai(): Description und Keywords mit Claude Haiku
   - _generate_description(): Heuristische Fallback-Methode
   - _extract_keywords(): Keyword-Extraktion mit Stopword-Filter
   - Automatischer Fallback wenn kein API-Key

8. **Sprach-Erkennung** ✅
   - _detect_language_from_html(): Liest lang-Attribut aus HTML
   - Unterstützt verschiedene Formate (de, de-DE, etc.)
   - Fallback auf og:locale und Meta-Tags

9. **Testing** ✅
   - Mit Krauchenwies.de getestet (Startseite)
   - Neue Asset-Struktur validiert
   - Icon-Filterung validiert (1 Bild statt 27)
   - JSON-pro-Asset Struktur funktioniert

## Notizen
- Fallback wenn kein ANTHROPIC_API_KEY: Warnung, aber trotzdem durchlaufen
- Progress-Anzeige für Downloads wichtig (kann viele Bilder sein)
- Timeout für große Dateien (z.B. 30 Sekunden)
- Max Dateigröße? (z.B. 50MB pro File)
