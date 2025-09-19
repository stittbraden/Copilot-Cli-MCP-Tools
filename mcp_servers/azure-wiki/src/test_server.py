#!/usr/bin/env python3
"""
Test script for Azure Wiki MCP server functionality.
Tests the search engine and MCP tools with sample wiki content.
"""

import sys
import os
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the search engine and tools directly for testing
from server import WikiSearchEngine, search_wiki, get_wiki_file, list_wiki_files, wiki_search_suggestions

def test_wiki_search():
    """Test the wiki search functionality."""
    
    print("🧪 Testing Azure Wiki MCP Server")
    print("=" * 50)
    
    # Initialize search engine with test docs
    docs_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs")
    engine = WikiSearchEngine(docs_path)
    
    # Test 1: List files
    print("\n📋 Test 1: List wiki files")
    result = list_wiki_files()
    print(f"Status: {result['status']}")
    print(f"Files found: {result['total_files']}")
    for file_info in result['files']:
        print(f"  - {file_info['name']} ({file_info['size']} bytes)")
    assert result['total_files'] > 0, "Should find at least some files"
    
    # Test 2: Search for Azure
    print("\n📋 Test 2: Search for 'Azure'")
    start_time = time.time()
    result = search_wiki("Azure", max_results=5)
    search_time = time.time() - start_time
    print(f"Status: {result['status']}")
    print(f"Results found: {result['total_found']}")
    print(f"Search time: {result['search_time']}s (actual: {search_time:.3f}s)")
    
    for i, match in enumerate(result['results'][:3], 1):
        print(f"  {i}. {match['title']} (score: {match['score']:.1f})")
        print(f"     File: {match['file']}")
        print(f"     Content: {match['content'][:100]}...")
    
    assert result['total_found'] > 0, "Should find Azure-related content"
    
    # Test 3: Search for specific term
    print("\n📋 Test 3: Search for 'Load Balancer'")
    result = search_wiki("Load Balancer")
    print(f"Status: {result['status']}")
    print(f"Results found: {result['total_found']}")
    
    if result['results']:
        best_match = result['results'][0]
        print(f"Best match: {best_match['title']} (score: {best_match['score']:.1f})")
    
    # Test 4: Get specific file content
    print("\n📋 Test 4: Get specific file content")
    result = get_wiki_file("azure-overview.md")
    print(f"Status: {result['status']}")
    print(f"File exists: {result['exists']}")
    print(f"Content size: {result['size']} bytes")
    if result['content']:
        print(f"Content preview: {result['content'][:100]}...")
    
    # Test 5: Search suggestions
    print("\n📋 Test 5: Search suggestions for 'azur'")
    result = wiki_search_suggestions("azur")
    print(f"Status: {result['status']}")
    print(f"Suggestions: {result['suggestions'][:5]}")
    
    # Test 6: File pattern search
    print("\n📋 Test 6: Search files matching '*.md'")
    result = list_wiki_files("*.md")
    print(f"Status: {result['status']}")
    print(f"Markdown files: {result['total_files']}")
    
    # Test 7: Performance test with multiple searches
    print("\n📋 Test 7: Performance test (10 searches)")
    queries = ["Azure", "VM", "Storage", "Network", "Virtual", "Load", "Gateway", "Subnet", "Security", "Scale"]
    
    start_time = time.time()
    total_results = 0
    for query in queries:
        result = search_wiki(query, max_results=3)
        total_results += result['total_found']
    
    total_time = time.time() - start_time
    avg_time = total_time / len(queries)
    
    print(f"Total search time: {total_time:.3f}s")
    print(f"Average per search: {avg_time:.3f}s")
    print(f"Total results across all searches: {total_results}")
    
    print("\n✅ All tests completed!")
    print(f"🚀 Performance: {avg_time:.3f}s average search time")

if __name__ == "__main__":
    test_wiki_search()