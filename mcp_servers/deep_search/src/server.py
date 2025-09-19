import asyncio
import os
import json
import re
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.filters import (
    FilterChain,
    DomainFilter,
    URLPatternFilter,
    ContentTypeFilter
)
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
from urllib.parse import urlparse
import httpx
from pathlib import Path
import ast
import subprocess

mcp = FastMCP("DeepSearch")

class CodeAnalyzer:
    """Analyzes code context and provides intelligent search assistance"""
    
    @staticmethod
    def extract_code_snippets(content: str) -> List[Dict[str, Any]]:
        """Extract code snippets from content with language detection"""
        snippets = []
        
        # Common code block patterns
        code_patterns = [
            r'```(\w+)?\n(.*?)```',  # Markdown code blocks
            r'<code[^>]*>(.*?)</code>',  # HTML code tags
            r'<pre[^>]*>(.*?)</pre>',   # HTML pre tags
        ]
        
        for pattern in code_patterns:
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                language = match.group(1) if len(match.groups()) > 1 else 'unknown'
                code = match.group(-1).strip()
                if len(code) > 10:  # Skip very short snippets
                    snippets.append({
                        'language': language or 'unknown',
                        'code': code[:1000],  # Limit size
                        'relevance_score': len(code) / 100  # Simple scoring
                    })
        
        return snippets
    
    @staticmethod
    def analyze_workspace_context(workspace_path: Optional[str] = None) -> Dict[str, Any]:
        """Analyze current workspace for context"""
        context = {
            'languages': [],
            'frameworks': [],
            'dependencies': {},
            'file_types': {},
        }
        
        if not workspace_path or not os.path.exists(workspace_path):
            workspace_path = os.getcwd()
        
        try:
            # Detect languages and frameworks from common files
            workspace = Path(workspace_path)
            
            # Check for common config files
            config_files = {
                'package.json': 'javascript',
                'requirements.txt': 'python',
                'Cargo.toml': 'rust',
                'go.mod': 'go',
                'pom.xml': 'java',
                'Gemfile': 'ruby',
                'composer.json': 'php',
            }
            
            for config_file, language in config_files.items():
                if (workspace / config_file).exists():
                    context['languages'].append(language)
                    
                    # Extract dependencies if possible
                    try:
                        if config_file == 'package.json':
                            with open(workspace / config_file) as f:
                                data = json.load(f)
                                context['dependencies']['npm'] = list(data.get('dependencies', {}).keys())[:10]
                        elif config_file == 'requirements.txt':
                            with open(workspace / config_file) as f:
                                deps = [line.split('==')[0].split('>=')[0].strip() 
                                       for line in f if line.strip() and not line.startswith('#')]
                                context['dependencies']['pip'] = deps[:10]
                    except Exception:
                        pass
            
            # Count file types
            for file_path in workspace.rglob('*'):
                if file_path.is_file() and not any(part.startswith('.') for part in file_path.parts):
                    ext = file_path.suffix.lower()
                    if ext:
                        context['file_types'][ext] = context['file_types'].get(ext, 0) + 1
            
            # Keep only top file types
            context['file_types'] = dict(sorted(context['file_types'].items(), 
                                              key=lambda x: x[1], reverse=True)[:10])
            
        except Exception as e:
            context['error'] = str(e)
        
        return context

@mcp.tool
async def smart_code_search(
    query: str, 
    workspace_path: Optional[str] = None,
    include_web: bool = True,
    include_local: bool = True,
    language_hint: Optional[str] = None
) -> Dict[str, Any]:
    """
    🔍 Intelligent multi-source code search that surpasses VSCode Copilot search capabilities.
    
    Searches Stack Overflow, GitHub repositories, local workspace files, and provides
    context-aware results with code snippets, relevance scoring, and smart suggestions.
    
    Args:
        query: Your search query (e.g., "async error handling", "React hooks best practices")
        workspace_path: Path to workspace for context analysis (optional, defaults to current directory)
        include_web: Search web sources like Stack Overflow and GitHub (default: True)
        include_local: Search local workspace files (default: True)  
        language_hint: Programming language filter (e.g., "python", "javascript", "go")
    
    Returns:
        Comprehensive results with ranked code snippets, sources, and related search suggestions
    """
    
    results = {
        'query': query,
        'context': {},
        'sources': [],
        'code_snippets': [],
        'explanations': [],
        'related_searches': []
    }
    
    # Analyze workspace context
    if include_local:
        results['context'] = CodeAnalyzer.analyze_workspace_context(workspace_path)
        if not language_hint and results['context']['languages']:
            language_hint = results['context']['languages'][0]
    
    # Search multiple sources in parallel
    search_tasks = []
    
    if include_web:
        # Search Stack Overflow
        search_tasks.append(_search_stackoverflow(query, language_hint))
        
        # Search GitHub if it's a code-related query
        if any(keyword in query.lower() for keyword in ['code', 'function', 'class', 'method', 'library', 'package']):
            search_tasks.append(_search_github(query, language_hint))
    
    if include_local and workspace_path:
        search_tasks.append(_search_local_files(query, workspace_path, language_hint))
    
    # Execute searches in parallel
    if search_tasks:
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        for result in search_results:
            if isinstance(result, dict) and not isinstance(result, Exception):
                if 'snippets' in result:
                    results['code_snippets'].extend(result['snippets'])
                if 'sources' in result:
                    results['sources'].extend(result['sources'])
                if 'explanations' in result:
                    results['explanations'].extend(result['explanations'])
    
    # Generate related search suggestions
    results['related_searches'] = _generate_related_searches(query, language_hint, results['context'])
    
    # Rank and limit results
    results['code_snippets'] = sorted(results['code_snippets'], 
                                    key=lambda x: x.get('relevance_score', 0), reverse=True)[:10]
    results['sources'] = results['sources'][:15]
    results['explanations'] = results['explanations'][:5]
    
    return results

async def _search_stackoverflow(query: str, language_hint: Optional[str] = None) -> Dict[str, Any]:
    """Search Stack Overflow for relevant questions and answers"""
    results = {'snippets': [], 'sources': [], 'explanations': []}
    
    try:
        # Use Stack Overflow API
        params = {
            'order': 'desc',
            'sort': 'relevance',
            'q': query,
            'site': 'stackoverflow',
            'filter': 'withbody'
        }
        
        if language_hint:
            params['tagged'] = language_hint
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                'https://api.stackexchange.com/2.3/search/advanced',
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                for item in data.get('items', [])[:5]:
                    # Extract code snippets from answers
                    body = item.get('body', '')
                    snippets = CodeAnalyzer.extract_code_snippets(body)
                    
                    for snippet in snippets[:2]:  # Limit snippets per answer
                        snippet['source'] = 'stackoverflow'
                        snippet['source_url'] = item.get('link', '')
                        snippet['title'] = item.get('title', '')
                        snippet['score'] = item.get('score', 0)
                        results['snippets'].append(snippet)
                    
                    # Add source info
                    results['sources'].append({
                        'title': item.get('title', ''),
                        'url': item.get('link', ''),
                        'source': 'Stack Overflow',
                        'score': item.get('score', 0),
                        'summary': body[:200] + '...' if len(body) > 200 else body
                    })
    
    except Exception as e:
        results['error'] = f"Stack Overflow search failed: {str(e)}"
    
    return results

async def _search_github(query: str, language_hint: Optional[str] = None) -> Dict[str, Any]:
    """Search GitHub for relevant code repositories and files"""
    results = {'snippets': [], 'sources': [], 'explanations': []}
    
    try:
        # Use GitHub search API (public, no auth required for basic search)
        search_query = f"{query}"
        if language_hint:
            search_query += f" language:{language_hint}"
        
        params = {
            'q': search_query,
            'sort': 'stars',
            'order': 'desc'
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                'https://api.github.com/search/repositories',
                params=params,
                timeout=10,
                headers={'Accept': 'application/vnd.github.v3+json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                for repo in data.get('items', [])[:3]:
                    results['sources'].append({
                        'title': repo.get('full_name', ''),
                        'url': repo.get('html_url', ''),
                        'source': 'GitHub Repository',
                        'stars': repo.get('stargazers_count', 0),
                        'description': repo.get('description', ''),
                        'language': repo.get('language', '')
                    })
    
    except Exception as e:
        results['error'] = f"GitHub search failed: {str(e)}"
    
    return results

async def _search_local_files(query: str, workspace_path: str, language_hint: Optional[str] = None) -> Dict[str, Any]:
    """Search local workspace files for relevant code"""
    results = {'snippets': [], 'sources': [], 'explanations': []}
    
    try:
        workspace = Path(workspace_path)
        if not workspace.exists():
            return results
        
        # File extensions to search based on language hint
        extensions = {
            'python': ['.py'],
            'javascript': ['.js', '.jsx', '.ts', '.tsx'],
            'java': ['.java'],
            'cpp': ['.cpp', '.c', '.h', '.hpp'],
            'csharp': ['.cs'],
            'go': ['.go'],
            'rust': ['.rs'],
            'php': ['.php'],
            'ruby': ['.rb'],
        }
        
        search_extensions = extensions.get(language_hint, ['.py', '.js', '.ts', '.java', '.cpp', '.go'])
        
        # Search for files containing the query
        query_words = query.lower().split()
        
        for file_path in workspace.rglob('*'):
            if (file_path.is_file() and 
                file_path.suffix.lower() in search_extensions and
                not any(part.startswith('.') for part in file_path.parts) and
                'node_modules' not in str(file_path)):
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        content_lower = content.lower()
                        
                        # Check if query words appear in the file
                        if any(word in content_lower for word in query_words):
                            # Extract relevant code snippets
                            lines = content.split('\n')
                            relevant_lines = []
                            
                            for i, line in enumerate(lines):
                                if any(word in line.lower() for word in query_words):
                                    # Include context around the match
                                    start = max(0, i - 3)
                                    end = min(len(lines), i + 4)
                                    snippet = '\n'.join(lines[start:end])
                                    
                                    results['snippets'].append({
                                        'language': language_hint or file_path.suffix[1:],
                                        'code': snippet,
                                        'source': 'local_file',
                                        'file_path': str(file_path.relative_to(workspace)),
                                        'line_number': i + 1,
                                        'relevance_score': sum(1 for word in query_words if word in line.lower())
                                    })
                                    
                                    if len(results['snippets']) >= 10:
                                        break
                                
                                if len(results['snippets']) >= 10:
                                    break
                
                except Exception:
                    continue  # Skip files that can't be read
        
        # Sort by relevance
        results['snippets'] = sorted(results['snippets'], 
                                   key=lambda x: x.get('relevance_score', 0), reverse=True)[:5]
    
    except Exception as e:
        results['error'] = f"Local file search failed: {str(e)}"
    
    return results

def _generate_related_searches(query: str, language_hint: Optional[str], context: Dict[str, Any]) -> List[str]:
    """Generate related search suggestions based on query and context"""
    suggestions = []
    
    # Language-specific suggestions
    if language_hint:
        suggestions.extend([
            f"{query} {language_hint} best practices",
            f"{query} {language_hint} examples",
            f"how to {query} in {language_hint}",
        ])
    
    # Framework-specific suggestions based on dependencies
    frameworks = context.get('dependencies', {})
    for fw_type, deps in frameworks.items():
        for dep in deps[:2]:  # Top 2 dependencies
            suggestions.append(f"{query} {dep}")
    
    # Common programming patterns
    common_patterns = [
        f"{query} tutorial",
        f"{query} documentation",
        f"{query} error handling",
        f"debug {query}",
        f"{query} performance optimization"
    ]
    suggestions.extend(common_patterns)
    
    return suggestions[:8]  # Limit suggestions

@mcp.tool
async def refine_search(
    original_query: str,
    feedback: str,
    previous_results: Optional[str] = None,
    workspace_path: Optional[str] = None,
    language_hint: Optional[str] = None
) -> Dict[str, Any]:
    """
    🎯 Refine and improve search results based on your feedback.
    
    Analyzes your feedback to create more targeted searches and better results.
    
    Args:
        original_query: Your original search query
        feedback: What you're looking for (e.g., "need more specific examples", "show TypeScript instead")
        previous_results: Previous search results JSON (optional)
        workspace_path: Path to workspace for context (optional)
        language_hint: Programming language preference (optional)
    
    Returns:
        Improved search results based on your feedback
    """
    
    # Parse previous results
    try:
        prev_results = json.loads(previous_results) if isinstance(previous_results, str) else previous_results
    except:
        prev_results = {}
    
    # Analyze feedback to create a better query
    refined_query = _analyze_feedback_and_refine_query(original_query, feedback, prev_results)
    
    # Execute refined search
    # Call the function implementation directly instead of the tool wrapper
    results = {
        'query': refined_query,
        'context': {},
        'sources': [],
        'code_snippets': [],
        'explanations': [],
        'related_searches': []
    }
    
    # Analyze workspace context
    if workspace_path:
        results['context'] = CodeAnalyzer.analyze_workspace_context(workspace_path)
        if not language_hint and results['context']['languages']:
            language_hint = results['context']['languages'][0]
    
    # Search multiple sources in parallel
    search_tasks = []
    
    # Search Stack Overflow
    search_tasks.append(_search_stackoverflow(refined_query, language_hint))
    
    # Search GitHub if it's a code-related query
    if any(keyword in refined_query.lower() for keyword in ['code', 'function', 'class', 'method', 'library', 'package']):
        search_tasks.append(_search_github(refined_query, language_hint))
    
    if workspace_path:
        search_tasks.append(_search_local_files(refined_query, workspace_path, language_hint))
    
    # Execute searches in parallel
    if search_tasks:
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        for result in search_results:
            if isinstance(result, dict) and not isinstance(result, Exception):
                if 'snippets' in result:
                    results['code_snippets'].extend(result['snippets'])
                if 'sources' in result:
                    results['sources'].extend(result['sources'])
                if 'explanations' in result:
                    results['explanations'].extend(result['explanations'])
    
    # Generate related search suggestions
    results['related_searches'] = _generate_related_searches(refined_query, language_hint, results['context'])
    
    # Rank and limit results
    results['code_snippets'] = sorted(results['code_snippets'], 
                                    key=lambda x: x.get('relevance_score', 0), reverse=True)[:10]
    results['sources'] = results['sources'][:15]
    results['explanations'] = results['explanations'][:5]
    
    return results

def _analyze_feedback_and_refine_query(original_query: str, feedback: str, prev_results: Dict) -> str:
    """Analyze user feedback to create a more targeted query"""
    
    feedback_lower = feedback.lower()
    
    # If user wants more specific results
    if any(word in feedback_lower for word in ['more specific', 'narrow down', 'exact', 'precise']):
        # Add more specific terms
        if 'code_snippets' in prev_results and prev_results['code_snippets']:
            # Extract common terms from successful snippets
            successful_code = ' '.join([snippet.get('code', '') for snippet in prev_results['code_snippets'][:3]])
            # Add common programming terms found
            common_terms = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', successful_code)
            if common_terms:
                refined_query = f"{original_query} {' '.join(common_terms[:3])}"
                return refined_query
    
    # If user wants examples or tutorials
    if any(word in feedback_lower for word in ['example', 'tutorial', 'how to', 'guide']):
        return f"{original_query} example tutorial how to"
    
    # If user wants different language/framework
    languages = ['python', 'javascript', 'java', 'go', 'rust', 'c++', 'typescript', 'php', 'ruby']
    for lang in languages:
        if lang in feedback_lower:
            return f"{original_query} {lang}"
    
    # If user wants error handling or debugging
    if any(word in feedback_lower for word in ['error', 'debug', 'troubleshoot', 'fix']):
        return f"{original_query} error handling debugging troubleshooting"
    
    # If user wants performance optimization
    if any(word in feedback_lower for word in ['performance', 'optimize', 'faster', 'efficient']):
        return f"{original_query} performance optimization efficient"
    
    # Default: combine original query with feedback
    return f"{original_query} {feedback}"

@mcp.tool
async def analyze_code_context(file_path: str, line_number: Optional[int] = None) -> Dict[str, Any]:
    """
    🧠 Analyze code context from a specific file and line to provide smart search suggestions.
    
    Performs deep code analysis including AST parsing, function/class extraction, and
    generates context-aware search suggestions based on your current code.
    
    Args:
        file_path: Path to the code file to analyze (relative or absolute)
        line_number: Specific line number to focus on (optional)
    
    Returns:
        Code analysis with functions, classes, imports, and intelligent search suggestions
    """
    
    result = {
        'file_path': file_path,
        'language': '',
        'imports': [],
        'functions': [],
        'classes': [],
        'variables': [],
        'context_summary': '',
        'search_suggestions': []
    }
    
    try:
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            result['error'] = 'File not found'
            return result
        
        # Detect language from extension
        ext = file_path_obj.suffix.lower()
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby'
        }
        
        result['language'] = language_map.get(ext, 'unknown')
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Python-specific analysis
        if result['language'] == 'python':
            try:
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            result['imports'].append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            result['imports'].append(node.module)
                    elif isinstance(node, ast.FunctionDef):
                        result['functions'].append({
                            'name': node.name,
                            'line': node.lineno,
                            'args': [arg.arg for arg in node.args.args]
                        })
                    elif isinstance(node, ast.ClassDef):
                        result['classes'].append({
                            'name': node.name,
                            'line': node.lineno
                        })
                        
            except SyntaxError:
                # Fallback to regex parsing
                pass
        
        # General regex-based analysis for all languages
        if not result['functions'] and not result['classes']:
            # Function patterns for different languages
            function_patterns = {
                'python': r'def\s+(\w+)\s*\(',
                'javascript': r'(?:function\s+(\w+)\s*\(|(\w+)\s*[:=]\s*(?:function\s*\(|async\s*\(|\([^)]*\)\s*=>))',
                'typescript': r'(?:function\s+(\w+)\s*\(|(\w+)\s*[:=]\s*(?:function\s*\(|async\s*\(|\([^)]*\)\s*=>))',
                'java': r'(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(',
                'go': r'func\s+(\w+)\s*\(',
                'rust': r'fn\s+(\w+)\s*\(',
                'cpp': r'(?:inline\s+)?(?:virtual\s+)?(?:static\s+)?\w+\s+(\w+)\s*\(',
                'csharp': r'(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\('
            }
            
            pattern = function_patterns.get(result['language'])
            if pattern:
                for i, line in enumerate(lines):
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        func_name = next(g for g in match.groups() if g)
                        if func_name:
                            result['functions'].append({
                                'name': func_name,
                                'line': i + 1
                            })
        
        # Generate context summary
        if line_number and 1 <= line_number <= len(lines):
            # Focus on specific line context
            start = max(0, line_number - 5)
            end = min(len(lines), line_number + 5)
            context_lines = lines[start:end]
            result['context_summary'] = f"Code around line {line_number}:\n" + '\n'.join(context_lines)
            
            # Find relevant functions/classes near this line
            nearby_functions = [f for f in result['functions'] 
                             if abs(f['line'] - line_number) <= 10]
            nearby_classes = [c for c in result['classes'] 
                            if abs(c['line'] - line_number) <= 20]
            
            # Generate search suggestions based on context
            current_line = lines[line_number - 1] if line_number <= len(lines) else ""
            
            suggestions = []
            if nearby_functions:
                func_name = nearby_functions[0]['name']
                suggestions.extend([
                    f"how to implement {func_name}",
                    f"{func_name} best practices",
                    f"testing {func_name}"
                ])
            
            # Extract keywords from current line
            keywords = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', current_line)
            for keyword in keywords[:3]:
                if len(keyword) > 3:  # Skip short words
                    suggestions.append(f"{keyword} {result['language']} documentation")
            
            result['search_suggestions'] = suggestions[:5]
        
        else:
            # General file summary
            result['context_summary'] = f"File contains {len(result['functions'])} functions, {len(result['classes'])} classes"
            if result['imports']:
                result['context_summary'] += f", imports: {', '.join(result['imports'][:5])}"
        
    except Exception as e:
        result['error'] = str(e)
    
    return result

@mcp.tool
async def deep_search(base_url: str, query: str, max_pages: int = 10, max_depth: int = 2) -> Dict[str, Any]:
    """
    🌐 Advanced web crawling with intelligent content discovery and relevance scoring.
    
    Performs deep website crawling to find pages most relevant to your query using
    sophisticated filtering and scoring algorithms.
    
    Args:
        base_url: The website URL to start crawling from (e.g., "https://docs.python.org")
        query: What you're searching for (e.g., "async programming tutorial")
        max_pages: Maximum number of pages to crawl (default: 10, max: 20)
        max_depth: How deep to crawl from the base URL (default: 2, max: 3)
    
    Returns:
        Ranked pages with titles, URLs, relevance scores, and content previews
    """
    try:
        # Safety limits
        max_pages = min(max_pages, 20)
        max_depth = min(max_depth, 3)
        
        # Parse the base URL to get domain
        parsed_url = urlparse(base_url)
        domain = parsed_url.netloc
        
        # Extract keywords from query for scoring
        query_keywords = query.lower().split()
        
        # Create a sophisticated filter chain
        filter_chain = FilterChain([
            # Domain boundaries - stay within the same domain
            DomainFilter(
                allowed_domains=[domain],
                blocked_domains=[]
            ),
            
            # Content type filtering - only HTML pages
            ContentTypeFilter(allowed_types=["text/html"])
        ])

        # Create a relevance scorer based on the query
        keyword_scorer = KeywordRelevanceScorer(
            keywords=query_keywords,
            weight=0.8
        )

        # Set up the configuration
        config = CrawlerRunConfig(
            deep_crawl_strategy=BestFirstCrawlingStrategy(
                max_depth=max_depth,
                include_external=False,
                filter_chain=filter_chain,
                url_scorer=keyword_scorer,
                max_pages=max_pages
            ),
            scraping_strategy=LXMLWebScrapingStrategy(),
            stream=True,
            verbose=False
        )

        # Execute the crawl
        results = []
        async with AsyncWebCrawler() as crawler:
            async for result in await crawler.arun(base_url, config=config):
                if result.success and result.html:
                    results.append(result)

        # Sort results by relevance score
        results.sort(key=lambda x: x.metadata.get("score", 0), reverse=True)

        # Format the response
        formatted_results = {
            "query": query,
            "base_url": base_url,
            "total_pages_found": len(results),
            "pages": []
        }

        for result in results[:max_pages]:
            page_info = {
                "url": result.url,
                "title": getattr(result, 'title', '') or 'No Title',
                "relevance_score": result.metadata.get("score", 0),
                "depth": result.metadata.get("depth", 0),
                "html_content": result.html[:5000] if result.html else "",  # Limit HTML content
                "text_content": result.markdown[:1000] if hasattr(result, 'markdown') else ""  # Preview of text
            }
            formatted_results["pages"].append(page_info)

        return formatted_results

    except Exception as e:
        return {
            "error": f"Failed to perform deep search: {str(e)}",
            "query": query,
            "base_url": base_url,
            "pages": []
        }

@mcp.tool
async def quick_search(query: str, language: Optional[str] = None) -> Dict[str, Any]:
    """
    ⚡ Quick search for immediate code help and examples.
    
    Fast search focusing on Stack Overflow answers and code snippets.
    Perfect for quick lookups and immediate problem solving.
    
    Args:
        query: What you need help with (e.g., "list comprehension", "promise chaining")
        language: Programming language (e.g., "python", "javascript") - optional
    
    Returns:
        Quick results with top code snippets and explanations
    """
    
    results = {
        'query': query,
        'language': language,
        'quick_snippets': [],
        'quick_explanations': [],
        'related_topics': []
    }
    
    try:
        # Quick Stack Overflow search
        so_results = await _search_stackoverflow(query, language)
        
        # Extract top snippets and explanations
        if so_results.get('snippets'):
            results['quick_snippets'] = so_results['snippets'][:3]
        
        if so_results.get('sources'):
            results['quick_explanations'] = [
                {
                    'title': source['title'],
                    'summary': source.get('summary', ''),
                    'url': source['url'],
                    'score': source.get('score', 0)
                }
                for source in so_results['sources'][:3]
            ]
        
        # Generate related topics
        if language:
            results['related_topics'] = [
                f"{query} {language} tutorial",
                f"{query} {language} best practices", 
                f"{query} {language} examples"
            ]
        else:
            results['related_topics'] = [
                f"{query} tutorial",
                f"{query} examples",
                f"how to {query}"
            ]
            
    except Exception as e:
        results['error'] = f"Quick search failed: {str(e)}"
    
    return results

if __name__ == "__main__":
    mcp.run()
