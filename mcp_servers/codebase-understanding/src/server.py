from fastmcp import FastMCP
import os
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime
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

def get_file_size(path: Path) -> str:
    """Get human readable file size."""
    try:
        size = path.stat().st_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
    except:
        return "0B"

def get_file_icon(path: Path) -> str:
    """Get emoji icon for file type."""
    if path.is_dir():
        return "📁"
    
    suffix = path.suffix.lower()
    icons = {
        '.py': '🐍', '.js': '🟨', '.ts': '🔷', '.jsx': '⚛️', '.tsx': '⚛️',
        '.html': '🌐', '.css': '🎨', '.scss': '🎨', '.sass': '🎨',
        '.json': '📋', '.xml': '📄', '.yaml': '📄', '.yml': '📄',
        '.md': '📝', '.txt': '📄', '.rst': '📄',
        '.sql': '🗄️', '.db': '🗄️', '.sqlite': '🗄️',
        '.jpg': '🖼️', '.jpeg': '🖼️', '.png': '🖼️', '.gif': '🖼️', '.svg': '🖼️',
        '.pdf': '📕', '.doc': '📘', '.docx': '📘',
        '.zip': '📦', '.tar': '📦', '.gz': '📦',
        '.sh': '⚙️', '.bat': '⚙️', '.ps1': '⚙️',
        '.env': '🔑', '.cfg': '⚙️', '.conf': '⚙️', '.ini': '⚙️',
        '.dockerfile': '🐳', '.gitignore': '🚫'
    }
    return icons.get(suffix, '📄')

@mcp.tool
def generate_folder_structure(root_path: str, max_depth: int = 5) -> str:
    """
    Generate a hierarchical folder structure tree with file metadata.
    
    Args:
        root_path: Path to the root directory to analyze
        max_depth: Maximum depth to traverse (default: 5)
    
    Returns:
        Formatted tree structure as markdown
    """
    root = Path(root_path).resolve()
    if not root.exists():
        return f"Error: Path '{root_path}' does not exist"
    
    lines = [f"# Folder Structure for {root.name}/\n"]
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    def build_tree(path: Path, prefix: str = "", depth: int = 0) -> List[str]:
        if depth > max_depth or should_exclude(path):
            return []
        
        tree_lines = []
        try:
            if path.is_file():
                icon = get_file_icon(path)
                size = get_file_size(path)
                tree_lines.append(f"{prefix}{icon} {path.name} ({size})")
            else:
                icon = get_file_icon(path)
                tree_lines.append(f"{prefix}{icon} {path.name}/")
                
                # Get children, sort directories first, then files
                children = []
                try:
                    children = sorted([p for p in path.iterdir() if not should_exclude(p)],
                                    key=lambda p: (p.is_file(), p.name.lower()))
                except PermissionError:
                    tree_lines.append(f"{prefix}├── ❌ Permission denied")
                    return tree_lines
                
                for i, child in enumerate(children):
                    is_last = i == len(children) - 1
                    child_prefix = prefix + ("└── " if is_last else "├── ")
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    
                    tree_lines.append(child_prefix + "")  # Add the connector
                    tree_lines[-1] = tree_lines[-1][:-1]  # Remove extra space
                    
                    if child.is_file():
                        icon = get_file_icon(child)
                        size = get_file_size(child)
                        tree_lines[-1] += f"{icon} {child.name} ({size})"
                    else:
                        child_tree = build_tree(child, next_prefix, depth + 1)
                        if child_tree:
                            icon = get_file_icon(child)
                            tree_lines[-1] += f"{icon} {child.name}/"
                            tree_lines.extend(child_tree)
                        else:
                            icon = get_file_icon(child)
                            tree_lines[-1] += f"{icon} {child.name}/"
                            
        except Exception as e:
            tree_lines.append(f"{prefix}❌ Error reading {path.name}: {str(e)}")
        
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
    Build a comprehensive dependency map of the codebase.
    
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
        "circular_dependencies": [],
        "entry_points": [],
        "generated": datetime.now().isoformat()
    }
    
    # Find all source files
    source_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.vue', '.java', '.c', '.cpp', '.cs', '.go', '.rs', '.rb', '.php'}
    
    def scan_directory(path: Path):
        for item in path.rglob('*'):
            if item.is_file() and not should_exclude(item) and item.suffix in source_extensions:
                relative_path = str(item.relative_to(root)).replace('\\', '/')
                
                # Determine file type
                file_type = "unknown"
                if item.name in ['main.py', 'app.py', 'server.py', 'index.js', 'main.js', 'app.js']:
                    file_type = "entry_point"
                    dependency_map["entry_points"].append(relative_path)
                elif 'test' in item.name.lower() or item.parent.name.lower() in ['tests', 'test']:
                    file_type = "test"
                elif item.suffix == '.py':
                    if 'util' in item.name.lower() or 'helper' in item.name.lower():
                        file_type = "utility"
                    else:
                        file_type = "module"
                elif item.suffix in ['.js', '.ts', '.jsx', '.tsx']:
                    if 'component' in item.name.lower():
                        file_type = "component"
                    elif 'util' in item.name.lower() or 'helper' in item.name.lower():
                        file_type = "utility"
                    else:
                        file_type = "module"
                
                # Extract imports
                local_imports = []
                external_deps = []
                
                if item.suffix == '.py':
                    local_imports, external_deps = extract_python_imports(item)
                elif item.suffix in ['.js', '.ts', '.jsx', '.tsx']:
                    local_imports, external_deps = extract_js_imports(item)
                
                dependency_map["files"][relative_path] = {
                    "imports": local_imports,
                    "imported_by": [],  # Will be populated in second pass
                    "external_deps": list(set(external_deps)),
                    "type": file_type,
                    "size": get_file_size(item)
                }
                
                # Track external dependencies
                for dep in external_deps:
                    if dep not in dependency_map["external_dependencies"]:
                        dependency_map["external_dependencies"][dep] = []
                    dependency_map["external_dependencies"][dep].append(relative_path)
    
    scan_directory(root)
    
    # Second pass: populate imported_by relationships
    for file_path, file_info in dependency_map["files"].items():
        for imported_file in file_info["imports"]:
            # Try to resolve relative imports to actual files
            for other_file in dependency_map["files"].keys():
                if imported_file in other_file or other_file.endswith(imported_file.replace('./', '') + '.py') or other_file.endswith(imported_file.replace('./', '') + '.js'):
                    dependency_map["files"][other_file]["imported_by"].append(file_path)
    
    # Simple circular dependency detection
    def has_circular_dependency(file_path: str, visited: Set[str], path: List[str]) -> bool:
        if file_path in visited:
            cycle_start = path.index(file_path)
            dependency_map["circular_dependencies"].append(path[cycle_start:] + [file_path])
            return True
        
        visited.add(file_path)
        path.append(file_path)
        
        if file_path in dependency_map["files"]:
            for imported in dependency_map["files"][file_path]["imports"]:
                for other_file in dependency_map["files"].keys():
                    if imported in other_file:
                        if has_circular_dependency(other_file, visited.copy(), path.copy()):
                            return True
        
        return False
    
    for file_path in dependency_map["files"].keys():
        has_circular_dependency(file_path, set(), [])
    
    # Remove duplicates from circular dependencies
    unique_cycles = []
    for cycle in dependency_map["circular_dependencies"]:
        if cycle not in unique_cycles:
            unique_cycles.append(cycle)
    dependency_map["circular_dependencies"] = unique_cycles
    
    return json.dumps(dependency_map, indent=2)

@mcp.tool
def create_component_analysis(root_path: str) -> str:
    """
    Create a comprehensive component analysis of the codebase.
    
    Args:
        root_path: Path to the root directory to analyze
    
    Returns:
        Markdown formatted component analysis
    """
    root = Path(root_path).resolve()
    if not root.exists():
        return f"Error: Path '{root_path}' does not exist"
    
    analysis = [f"# Component Analysis for {root.name}"]
    analysis.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Find entry points
    entry_points = []
    config_files = []
    test_files = []
    doc_files = []
    core_modules = []
    
    for item in root.rglob('*'):
        if item.is_file() and not should_exclude(item):
            relative_path = str(item.relative_to(root)).replace('\\', '/')
            
            # Entry points
            if item.name in ['main.py', 'app.py', 'server.py', 'index.js', 'main.js', 'app.js', '__main__.py']:
                entry_points.append(f"- `{relative_path}` - {item.name}")
            elif item.suffix == '.py' and item.name.endswith('_main.py'):
                entry_points.append(f"- `{relative_path}` - Main module")
            
            # Configuration files
            elif item.name in ['package.json', 'requirements.txt', 'setup.py', 'pyproject.toml', 'Dockerfile', 'docker-compose.yml']:
                config_files.append(f"- `{relative_path}` - {item.name}")
            elif item.suffix in ['.env', '.cfg', '.conf', '.ini', '.yaml', '.yml'] and 'config' in item.name.lower():
                config_files.append(f"- `{relative_path}` - Configuration")
            
            # Test files
            elif 'test' in item.name.lower() or item.parent.name.lower() in ['tests', 'test', 'spec']:
                test_files.append(f"- `{relative_path}` - Test file")
            
            # Documentation
            elif item.suffix in ['.md', '.rst', '.txt'] or item.name.lower() in ['readme', 'changelog', 'license']:
                doc_files.append(f"- `{relative_path}` - Documentation")
            
            # Core modules (heuristic based)
            elif item.suffix in ['.py', '.js', '.ts'] and not any(x in item.name.lower() for x in ['test', 'spec', 'mock']):
                if any(keyword in item.name.lower() for keyword in ['core', 'base', 'main', 'app', 'service', 'controller', 'model']):
                    core_modules.append(f"- `{relative_path}` - Core module")
    
    # Build analysis sections
    analysis.append("## Entry Points")
    if entry_points:
        analysis.extend(entry_points)
    else:
        analysis.append("- No clear entry points identified")
    
    analysis.append("\n## Core Modules")
    if core_modules:
        analysis.extend(core_modules[:10])  # Limit to top 10
        if len(core_modules) > 10:
            analysis.append(f"- ... and {len(core_modules) - 10} more")
    else:
        analysis.append("- No core modules identified")
    
    analysis.append("\n## Configuration Files")
    if config_files:
        analysis.extend(config_files)
    else:
        analysis.append("- No configuration files identified")
    
    analysis.append("\n## Test Files")
    if test_files:
        analysis.extend(test_files[:10])  # Limit to top 10
        if len(test_files) > 10:
            analysis.append(f"- ... and {len(test_files) - 10} more")
    else:
        analysis.append("- No test files identified")
    
    analysis.append("\n## Documentation")
    if doc_files:
        analysis.extend(doc_files)
    else:
        analysis.append("- No documentation files identified")
    
    return "\n".join(analysis)

@mcp.tool
def create_codebase_index(root_path: str, max_depth: int = 5) -> str:
    """
    Create a complete codebase index by running all analysis tools and saving results.
    
    Args:
        root_path: Path to the root directory to analyze
        max_depth: Maximum depth for folder structure (default: 5)
    
    Returns:
        Summary of the indexing operation
    """
    root = Path(root_path).resolve()
    if not root.exists():
        return f"Error: Path '{root_path}' does not exist"
    
    # Create .codebase-index directory
    index_dir = root / '.codebase-index'
    index_dir.mkdir(exist_ok=True)
    
    try:
        # Generate folder structure
        structure = generate_folder_structure(str(root), max_depth)
        with open(index_dir / 'structure.md', 'w', encoding='utf-8') as f:
            f.write(structure)
        
        # Build dependency map
        dependencies = build_dependency_map(str(root))
        with open(index_dir / 'dependencies.json', 'w', encoding='utf-8') as f:
            f.write(dependencies)
        
        # Create component analysis
        components = create_component_analysis(str(root))
        with open(index_dir / 'components.md', 'w', encoding='utf-8') as f:
            f.write(components)
        
        # Create timestamp file
        with open(index_dir / 'index.timestamp', 'w') as f:
            f.write(datetime.now().isoformat())
        
        # Generate summary
        dep_data = json.loads(dependencies)
        file_count = len(dep_data.get('files', {}))
        external_deps = len(dep_data.get('external_dependencies', {}))
        entry_points = len(dep_data.get('entry_points', []))
        
        summary = f"""# Codebase Index Generated Successfully

**Project:** {root.name}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Location:** `{index_dir.relative_to(root)}/`

## Summary Statistics
- **Source Files Analyzed:** {file_count}
- **External Dependencies:** {external_deps}
- **Entry Points Identified:** {entry_points}
- **Circular Dependencies:** {len(dep_data.get('circular_dependencies', []))}

## Generated Files
- `structure.md` - Visual folder tree with file metadata
- `dependencies.json` - Machine-readable dependency graph
- `components.md` - Human-readable component overview
- `index.timestamp` - Generation timestamp

## Usage
Reference these files during development to:
- Understand project layout and organization
- Identify dependencies before making changes
- Locate appropriate places for new functionality
- Understand component relationships and architecture

The index should be regenerated when significant structural changes are made to the codebase.
"""
        
        return summary
        
    except Exception as e:
        return f"Error creating codebase index: {str(e)}"

if __name__ == "__main__":
    mcp.run()