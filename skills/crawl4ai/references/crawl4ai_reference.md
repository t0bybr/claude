# Crawl4AI Reference

## Installation

```bash
pip install crawl4ai --break-system-packages
```

## Basic Usage

### Async Crawler (Recommended)

```python
from crawl4ai import AsyncWebCrawler

async with AsyncWebCrawler(verbose=True) as crawler:
    result = await crawler.arun(url="https://example.com")
    
    if result.success:
        print(result.markdown)  # Clean markdown content
        print(result.html)      # Raw HTML
        print(result.links)     # Extracted links
```

## Key Parameters

### arun() Parameters

- **url**: str - URL to crawl
- **bypass_cache**: bool - Force fresh fetch (default: False)
- **wait_for**: float - Seconds to wait for JavaScript rendering
- **screenshot**: bool - Capture page screenshot
- **css_selector**: str - Extract specific element(s)
- **word_count_threshold**: int - Minimum words to extract
- **excluded_tags**: list - HTML tags to exclude ['nav', 'footer', 'header']

## Result Object

### Main Properties

- **success**: bool - Whether crawl succeeded
- **html**: str - Raw HTML content
- **markdown**: str - Converted markdown
- **cleaned_html**: str - HTML with boilerplate removed
- **links**: dict - Internal and external links
  - `internal`: list of dicts with 'href' and 'text'
  - `external`: list of dicts with 'href' and 'text'
- **media**: dict - Images, videos, audio
- **metadata**: dict - Page metadata (title, description, etc.)
- **screenshot**: bytes - Page screenshot if requested
- **error_message**: str - Error details if failed

## Content Extraction Strategies

### CSS Selector Strategy

```python
result = await crawler.arun(
    url="https://example.com",
    css_selector="article.main-content"
)
```

### Exclude Elements

```python
result = await crawler.arun(
    url="https://example.com",
    excluded_tags=['nav', 'footer', 'aside', 'header']
)
```

## Link Extraction

Links are automatically extracted and categorized:

```python
if result.links:
    for link in result.links['internal']:
        print(f"{link['text']}: {link['href']}")
    
    for link in result.links['external']:
        print(f"External: {link['text']}: {link['href']}")
```

## Performance Tips

1. **Use bypass_cache=True** for fresh content
2. **Adjust wait_for** based on site's JavaScript needs (1-10 seconds)
3. **Use css_selector** to extract specific sections
4. **Exclude unnecessary tags** to reduce processing time
5. **Reuse AsyncWebCrawler** instance for multiple URLs

## Common Patterns

### Recursive Crawling

```python
async def crawl_recursively(start_url, max_depth=3):
    visited = set()
    to_visit = [(start_url, 0)]
    
    async with AsyncWebCrawler() as crawler:
        while to_visit:
            url, depth = to_visit.pop(0)
            
            if url in visited or depth > max_depth:
                continue
            
            visited.add(url)
            result = await crawler.arun(url=url)
            
            # Process result...
            
            # Add child links
            if result.links:
                for link in result.links['internal']:
                    to_visit.append((link['href'], depth + 1))
```

### Content Cleaning

```python
# Extract main content only
result = await crawler.arun(
    url=url,
    css_selector="main, article, .content",
    excluded_tags=['nav', 'footer', 'header', 'aside']
)

# Already in markdown format
clean_content = result.markdown
```

## Error Handling

```python
result = await crawler.arun(url=url)

if result.success:
    # Process content
    pass
else:
    print(f"Error: {result.error_message}")
```

## Domain Filtering

```python
from urllib.parse import urlparse

base_domain = urlparse(start_url).netloc

for link in result.links['internal']:
    link_domain = urlparse(link['href']).netloc
    if link_domain == base_domain:
        # Process same-domain link
        pass
```
