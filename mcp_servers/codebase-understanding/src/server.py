from fastmcp import FastMCP
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple
import ast

mcp = FastMCP("Codebase Understanding MCP Server")

# Common files and directories to exclude from analysis
EXCLUDE_PATTERNS = {
    '.git', '.gitignore', '.github', 'node_modules', '__pycache__', '.pytest_cache',
    'dist', 'build', '.venv', 'venv', '.env', '.idea', '.vscode', '.DS_Store',
    '*.pyc', '*.pyo', '*.pyd', '.coverage', 'coverage.xml', '.tox', '.mypy_cache',
    '.eslintcache', 'package-lock.json', 'yarn.lock', '.next', '.nuxt', 'target',
    'bin', 'obj', '*.class', '*.jar', '*.war', '*.exe', '*.dll', '*.so', '*.dylib'
}

def should_exclude(path: Path) -> bool:
    """Check if a path should be excluded from analysis."""
    name = path.name
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith('*'):
            if name.endswith(pattern[1:]):
                return True
        elif name == pattern:
            return True
    return False

@mcp.tool
def generate_folder_structure(root_path: str, max_depth: int = 3) -> str:
    """
    Generate a simple hierarchical folder structure tree.
    
    Args:
        root_path: Path to the root directory to analyze
        max_depth: Maximum depth to traverse (default: 3)
    
    Returns:
        Formatted tree structure as text
    """
    root = Path(root_path).resolve()
    if not root.exists():
        return f"Error: Path '{root_path}' does not exist"
    
    lines = [f"Folder Structure for {root.name}/\n"]
    
    def build_tree(path: Path, prefix: str = "", depth: int = 0) -> List[str]:
        if depth > max_depth or should_exclude(path):
            return []
        
        tree_lines = []
        try:
            if path.is_file():
                tree_lines.append(f"{prefix}{path.name}")
            else:
                tree_lines.append(f"{prefix}{path.name}/")
                
                # Get children, sort directories first, then files
                children = []
                try:
                    children = sorted([p for p in path.iterdir() if not should_exclude(p)],
                                    key=lambda p: (p.is_file(), p.name.lower()))
                except PermissionError:
                    tree_lines.append(f"{prefix}├── Permission denied")
                    return tree_lines
                
                for i, child in enumerate(children):
                    is_last = i == len(children) - 1
                    child_prefix = prefix + ("└── " if is_last else "├── ")
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    
                    if child.is_file():
                        tree_lines.append(f"{child_prefix}{child.name}")
                    else:
                        child_tree = build_tree(child, next_prefix, depth + 1)
                        tree_lines.append(f"{child_prefix}{child.name}/")
                        tree_lines.extend(child_tree)
                            
        except Exception as e:
            tree_lines.append(f"{prefix}Error reading {path.name}: {str(e)}")
        
        return tree_lines
    
    tree_lines = build_tree(root)
    lines.extend(tree_lines)
    
    return "\n".join(lines)

def extract_python_imports(file_path: Path) -> Tuple[List[str], List[str]]:
    """Extract imports from a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        local_imports = []
        external_imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    external_imports.append(name.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    if node.level > 0 or node.module.startswith('.'):
                        # Relative import
                        local_imports.append(node.module)
                    else:
                        # External import
                        external_imports.append(node.module.split('.')[0])
                        
        return local_imports, external_imports
    except:
        return [], []

def extract_js_imports(file_path: Path) -> Tuple[List[str], List[str]]:
    """Extract imports from JavaScript/TypeScript files."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        local_imports = []
        external_imports = []
        
        # Match import statements
        import_patterns = [
            r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        ]
        
        for pattern in import_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if match.startswith('.'):
                    local_imports.append(match)
                else:
                    external_imports.append(match.split('/')[0])
                    
        return local_imports, external_imports
    except:
        return [], []

@mcp.tool
def build_dependency_map(root_path: str) -> str:
    """
    Build a simple dependency map of the codebase.
    
    Args:
        root_path: Path to the root directory to analyze
    
    Returns:
        JSON string containing the dependency map
    """
    root = Path(root_path).resolve()
    if not root.exists():
        return json.dumps({"error": f"Path '{root_path}' does not exist"})
    
    dependency_map = {
        "files": {},
        "external_dependencies": {},
        "entry_points": []
    }
    
    # Find all source files
    source_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.vue', '.java', '.c', '.cpp', '.cs', '.go', '.rs', '.rb', '.php'}
    
    def scan_directory(path: Path):
        for item in path.rglob('*'):
            if item.is_file() and not should_exclude(item) and item.suffix in source_extensions:
                relative_path = str(item.relative_to(root)).replace('\\', '/')
                
                # Check if it's an entry point
                if item.name in ['main.py', 'app.py', 'server.py', 'index.js', 'main.js', 'app.js']:
                    dependency_map["entry_points"].append(relative_path)
                
                # Extract imports
                local_imports = []
                external_deps = []
                
                if item.suffix == '.py':
                    local_imports, external_deps = extract_python_imports(item)
                elif item.suffix in ['.js', '.ts', '.jsx', '.tsx']:
                    local_imports, external_deps = extract_js_imports(item)
                
                dependency_map["files"][relative_path] = {
                    "imports": local_imports,
                    "external_deps": list(set(external_deps))
                }
                
                # Track external dependencies
                for dep in external_deps:
                    if dep not in dependency_map["external_dependencies"]:
                        dependency_map["external_dependencies"][dep] = []
                    dependency_map["external_dependencies"][dep].append(relative_path)
    
    scan_directory(root)
    
    return json.dumps(dependency_map, indent=2)

if __name__ == "__main__":
    mcp.run()