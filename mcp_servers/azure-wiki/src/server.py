import os
import re
import mmap
import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from functools import lru_cache
import fnmatch
from fastmcp import FastMCP

mcp = FastMCP("Azure Wiki MCP Server")

class WikiSearchEngine:
    """
    High-performance wiki search engine designed for large documentation sets.
    Uses lazy indexing, memory-mapped files, and smart caching for speed.
    """
    
    def __init__(self, docs_path: str):
        self.docs_path = Path(docs_path)
        self.file_cache = {}  # LRU cache for file contents
        self.index_cache = {}  # Cached file indexes
        self.file_stats = {}  # File modification times for cache invalidation
        self.bloom_filter = set()  # Simple bloom filter for quick negative lookups
        self.max_cache_size = 50  # Maximum files to keep in memory
        
    def _get_all_files(self, extensions: List[str] = None) -> List[Path]:
        """Get all documentation files, optionally filtered by extension."""
        if extensions is None:
            extensions = ['.md', '.txt', '.rst', '.html', '.xml']
        
        files = []
        if not self.docs_path.exists():
            return files
            
        for ext in extensions:
            pattern = f"**/*{ext}"
            files.extend(self.docs_path.glob(pattern))
        
        return sorted(files)
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Get a hash of file path and modification time for cache keys."""
        try:
            stat = file_path.stat()
            content = f"{file_path}:{stat.st_mtime}:{stat.st_size}"
            return hashlib.md5(content.encode()).hexdigest()
        except (OSError, IOError):
            return hashlib.md5(str(file_path).encode()).hexdigest()
    
    def _read_file_chunked(self, file_path: Path, chunk_size: int = 8192) -> str:
        """Read file in chunks to handle large files efficiently."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except (OSError, IOError, UnicodeDecodeError):
            try:
                # Try with different encoding
                with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
                    return f.read()
            except:
                return ""
    
    def _extract_sections(self, content: str, file_path: Path) -> List[Dict]:
        """Extract sections with headers for better search results."""
        sections = []
        lines = content.split('\n')
        current_section = {"title": str(file_path.name), "content": [], "level": 0}
        
        for line_num, line in enumerate(lines, 1):
            # Detect markdown headers
            if line.strip().startswith('#'):
                # Save previous section
                if current_section["content"]:
                    current_section["content"] = '\n'.join(current_section["content"])
                    sections.append(current_section.copy())
                
                # Start new section
                level = len(line) - len(line.lstrip('#'))
                title = line.strip('#').strip()
                current_section = {
                    "title": title,
                    "content": [],
                    "level": level,
                    "line": line_num,
                    "file": str(file_path.relative_to(self.docs_path))
                }
            else:
                current_section["content"].append(line)
        
        # Add final section
        if current_section["content"]:
            current_section["content"] = '\n'.join(current_section["content"])
            sections.append(current_section)
        
        return sections
    
    def _build_word_index(self, content: str) -> Set[str]:
        """Build a set of searchable words from content."""
        # Simple word extraction - could be enhanced with stemming/lemmatization
        words = set()
        # Extract words (alphanumeric + common punctuation)
        word_pattern = re.compile(r'\b\w{2,}\b', re.IGNORECASE)
        for word in word_pattern.findall(content.lower()):
            words.add(word)
            # Add to bloom filter for quick negative lookups
            self.bloom_filter.add(word)
        return words
    
    def search_files(self, query: str, max_results: int = 10, file_pattern: str = "*") -> List[Dict]:
        """
        Search for query across all wiki files.
        Returns list of matching sections with relevance scoring.
        """
        query_words = set(re.findall(r'\b\w{2,}\b', query.lower()))
        
        # Quick bloom filter check
        if not any(word in self.bloom_filter for word in query_words):
            return []
        
        results = []
        files = self._get_all_files()
        
        # Filter files by pattern if specified
        if file_pattern != "*":
            files = [f for f in files if fnmatch.fnmatch(f.name, file_pattern)]
        
        for file_path in files:
            file_hash = self._get_file_hash(file_path)
            
            # Check cache first
            if file_hash in self.index_cache:
                sections = self.index_cache[file_hash]
            else:
                # Read and index file
                content = self._read_file_chunked(file_path)
                if not content:
                    continue
                    
                sections = self._extract_sections(content, file_path)
                
                # Add word index to each section
                for section in sections:
                    section["words"] = self._build_word_index(section["content"])
                
                # Cache the indexed sections
                self.index_cache[file_hash] = sections
                
                # Limit cache size
                if len(self.index_cache) > self.max_cache_size:
                    # Remove oldest entry (simple LRU approximation)
                    oldest_key = next(iter(self.index_cache))
                    del self.index_cache[oldest_key]
            
            # Search within sections
            for section in sections:
                score = self._calculate_relevance(section, query_words, query)
                if score > 0:
                    result = {
                        "file": section.get("file", str(file_path.relative_to(self.docs_path))),
                        "title": section["title"],
                        "content": section["content"][:500] + "..." if len(section["content"]) > 500 else section["content"],
                        "score": score,
                        "line": section.get("line", 1),
                        "level": section.get("level", 0)
                    }
                    results.append(result)
        
        # Sort by relevance score and return top results
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]
    
    def _calculate_relevance(self, section: Dict, query_words: Set[str], original_query: str) -> float:
        """Calculate relevance score for a section."""
        content = section["content"].lower()
        title = section["title"].lower()
        words = section.get("words", set())
        
        score = 0.0
        
        # Exact phrase match (highest priority)
        if original_query.lower() in content:
            score += 10.0
        if original_query.lower() in title:
            score += 15.0
        
        # Word matches in content
        word_matches = len(query_words.intersection(words))
        if word_matches > 0:
            score += word_matches * 2.0
        
        # Word matches in title (higher weight)
        title_words = set(re.findall(r'\b\w{2,}\b', title))
        title_matches = len(query_words.intersection(title_words))
        if title_matches > 0:
            score += title_matches * 5.0
        
        # Bonus for higher-level headers (more important sections)
        if section.get("level", 0) <= 2:
            score *= 1.2
        
        return score
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """Get full content of a specific file."""
        full_path = self.docs_path / file_path
        if not full_path.exists():
            return None
        return self._read_file_chunked(full_path)
    
    def list_files(self, pattern: str = "*", max_files: int = 100) -> List[Dict]:
        """List files in the wiki with basic metadata."""
        files = self._get_all_files()
        
        if pattern != "*":
            files = [f for f in files if fnmatch.fnmatch(f.name, pattern)]
        
        result = []
        for file_path in files[:max_files]:
            try:
                stat = file_path.stat()
                result.append({
                    "path": str(file_path.relative_to(self.docs_path)),
                    "name": file_path.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "extension": file_path.suffix
                })
            except (OSError, IOError):
                continue
        
        return result

# Initialize the search engine
docs_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs")
search_engine = WikiSearchEngine(docs_path)

@mcp.tool
def search_wiki(
    query: str,
    max_results: int = 10,
    file_pattern: str = "*"
) -> Dict:
    """
    Search the Azure wiki documentation for relevant content.
    
    Args:
        query: Search terms or phrase to find in the documentation
        max_results: Maximum number of results to return (default: 10)
        file_pattern: File name pattern to filter search (e.g., "*.md", "*azure*")
    
    Returns:
        Dict containing:
        - results: List of matching sections with file, title, content, and relevance score
        - total_found: Total number of matches found
        - search_time: Time taken to perform the search
        - query_used: The query that was searched
    """
    start_time = time.time()
    
    try:
        results = search_engine.search_files(query, max_results, file_pattern)
        search_time = time.time() - start_time
        
        return {
            "results": results,
            "total_found": len(results),
            "search_time": round(search_time, 3),
            "query_used": query,
            "status": "success"
        }
    except Exception as e:
        return {
            "results": [],
            "total_found": 0,
            "search_time": time.time() - start_time,
            "query_used": query,
            "status": "error",
            "error": str(e)
        }

@mcp.tool
def get_wiki_file(file_path: str) -> Dict:
    """
    Get the full content of a specific wiki file.
    
    Args:
        file_path: Relative path to the file from the docs directory
    
    Returns:
        Dict containing:
        - content: Full file content
        - file_path: The requested file path
        - exists: Whether the file exists
        - size: File size in bytes (if exists)
    """
    try:
        content = search_engine.get_file_content(file_path)
        if content is None:
            return {
                "content": "",
                "file_path": file_path,
                "exists": False,
                "size": 0,
                "status": "File not found"
            }
        
        return {
            "content": content,
            "file_path": file_path,
            "exists": True,
            "size": len(content.encode('utf-8')),
            "status": "success"
        }
    except Exception as e:
        return {
            "content": "",
            "file_path": file_path,
            "exists": False,
            "size": 0,
            "status": f"error: {str(e)}"
        }

@mcp.tool
def list_wiki_files(
    pattern: str = "*",
    max_files: int = 100
) -> Dict:
    """
    List files in the wiki documentation.
    
    Args:
        pattern: File name pattern to match (e.g., "*.md", "*azure*")
        max_files: Maximum number of files to return
    
    Returns:
        Dict containing:
        - files: List of file information (path, name, size, modified time)
        - total_files: Total number of files found
        - pattern_used: The pattern that was used for filtering
    """
    try:
        files = search_engine.list_files(pattern, max_files)
        
        return {
            "files": files,
            "total_files": len(files),
            "pattern_used": pattern,
            "status": "success"
        }
    except Exception as e:
        return {
            "files": [],
            "total_files": 0,
            "pattern_used": pattern,
            "status": f"error: {str(e)}"
        }

@mcp.tool
def wiki_search_suggestions(partial_query: str) -> Dict:
    """
    Get search suggestions based on partial query by analyzing available content.
    
    Args:
        partial_query: Partial search term to get suggestions for
    
    Returns:
        Dict containing:
        - suggestions: List of suggested search terms
        - based_on: The partial query used
    """
    try:
        # Simple suggestion system based on bloom filter content
        suggestions = []
        partial_lower = partial_query.lower()
        
        # Find words in bloom filter that start with the partial query
        matching_words = [word for word in search_engine.bloom_filter 
                         if word.startswith(partial_lower) and len(word) > len(partial_lower)]
        
        # Sort by length (shorter = more likely to be useful) and take top 10
        suggestions = sorted(matching_words, key=len)[:10]
        
        return {
            "suggestions": suggestions,
            "based_on": partial_query,
            "status": "success"
        }
    except Exception as e:
        return {
            "suggestions": [],
            "based_on": partial_query,
            "status": f"error: {str(e)}"
        }

if __name__ == "__main__":
    mcp.run()