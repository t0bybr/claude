#!/usr/bin/env python3
"""
Analyze website structure before full crawl.
Usage: python analyze_structure.py <url> [--max-depth N]
"""
import asyncio
import sys
import json
from urllib.parse import urlparse, urljoin
from collections import defaultdict

async def analyze_structure(base_url: str, max_depth: int = 3):
    """
    Analyze website structure without downloading full content.
    
    Args:
        base_url: Starting URL to analyze
        max_depth: Maximum depth to crawl (default: 3)
    
    Returns:
        Dictionary with structure information
    """
    from crawl4ai import AsyncWebCrawler
    
    base_domain = urlparse(base_url).netloc
    visited = set()
    to_visit = [(base_url, 0)]  # (url, depth)
    structure = defaultdict(lambda: {"children": [], "depth": 0, "title": ""})
    
    stats = {
        "total_pages": 0,
        "by_depth": defaultdict(int),
        "estimated_time_seconds": 0,
        "domains": set([base_domain])
    }
    
    print(f"🔍 Analyzing structure of: {base_url}")
    print(f"   Max depth: {max_depth}\n")
    
    async with AsyncWebCrawler(verbose=False) as crawler:
        while to_visit:
            current_url, depth = to_visit.pop(0)
            
            if current_url in visited or depth > max_depth:
                continue
                
            visited.add(current_url)
            stats["total_pages"] += 1
            stats["by_depth"][depth] += 1
            
            # Get page info
            result = await crawler.arun(
                url=current_url,
                bypass_cache=True,
                wait_for=1.0
            )
            
            if not result.success:
                print(f"⚠ Failed to analyze: {current_url}")
                continue
            
            # Extract title
            title = result.metadata.get('title', 'No title')
            structure[current_url]["title"] = title
            structure[current_url]["depth"] = depth
            
            print(f"{'  ' * depth}📄 [{depth}] {title}")
            print(f"{'  ' * depth}    {current_url}")
            
            # Extract internal links for next level
            if depth < max_depth and result.links:
                internal_links = result.links.get('internal', [])
                for link in internal_links:
                    link_url = link.get('href', '')
                    if not link_url:
                        continue
                    
                    # Ensure absolute URL
                    full_url = urljoin(current_url, link_url)
                    link_domain = urlparse(full_url).netloc
                    
                    # Only follow links within same domain
                    if link_domain == base_domain and full_url not in visited:
                        to_visit.append((full_url, depth + 1))
                        structure[current_url]["children"].append(full_url)
    
    # Calculate estimates
    stats["estimated_time_seconds"] = stats["total_pages"] * 6  # ~5s per page + overhead
    stats["domains"] = list(stats["domains"])
    stats["by_depth"] = dict(stats["by_depth"])
    
    # Print summary
    print("\n" + "="*60)
    print("📊 STRUCTURE ANALYSIS SUMMARY")
    print("="*60)
    print(f"Total pages found: {stats['total_pages']}")
    print(f"Pages by depth:")
    for d in sorted(stats["by_depth"].keys()):
        print(f"  Level {d}: {stats['by_depth'][d]} pages")
    print(f"\nEstimated crawl time: ~{stats['estimated_time_seconds']//60} minutes {stats['estimated_time_seconds']%60} seconds")
    print(f"Domain: {base_domain}")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    if stats["total_pages"] > 100:
        print("  ⚠ Large site detected! Consider:")
        print("    - Reducing max-depth")
        print("    - Crawling by main sections separately")
        print("    - Using --single-page for testing first")
    elif stats["total_pages"] > 50:
        print("  ⚠ Medium-sized site. Full crawl will take some time.")
        print("    Consider testing with a smaller section first.")
    else:
        print("  ✓ Reasonable size for full crawl in one go.")
    
    return {"stats": stats, "structure": dict(structure)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_structure.py <url> [--max-depth N]")
        sys.exit(1)
    
    url = sys.argv[1]
    max_depth = 3
    
    if "--max-depth" in sys.argv:
        idx = sys.argv.index("--max-depth")
        if idx + 1 < len(sys.argv):
            max_depth = int(sys.argv[idx + 1])
    
    result = asyncio.run(analyze_structure(url, max_depth))
    
    # Save structure to JSON for reference
    with open("site_structure.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Full structure saved to: site_structure.json")
