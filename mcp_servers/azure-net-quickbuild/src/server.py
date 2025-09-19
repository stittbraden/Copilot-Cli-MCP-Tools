import asyncio
import subprocess
import os
import re
from typing import Dict, List, Optional
from fastmcp import FastMCP

mcp = FastMCP("Azure Net Quickbuild MCP Server")

class QuickBuildError:
    def __init__(self, file_path: str, line_number: Optional[int], error_message: str):
        self.file_path = file_path
        self.line_number = line_number
        self.error_message = error_message
    
    def to_dict(self) -> Dict:
        return {
            "file": self.file_path,
            "line": self.line_number,
            "message": self.error_message
        }

@mcp.tool
def azure_net_quickbuild(
    project_directory: str,
    timeout_minutes: int = 10
) -> Dict:
    """
    Runs Azure .NET QuickBuild in debug mode to test project compilation.
    
    Args:
        project_directory: The absolute path to the directory containing the .NET project
        timeout_minutes: Maximum time to wait for build completion (default: 10 minutes)
    
    Returns:
        Dict containing:
        - success: bool indicating if build succeeded
        - errors: List of error objects with file, line, and message
        - raw_output: The complete build output for debugging
        - status: Human-readable status message
    """
    
    # Validate directory exists
    if not os.path.exists(project_directory):
        return {
            "success": False,
            "errors": [{"file": "", "line": None, "message": f"Project directory not found: {project_directory}"}],
            "raw_output": "",
            "status": "❌ Project directory not found"
        }
    
    # Validate directory is accessible
    if not os.path.isdir(project_directory):
        return {
            "success": False,
            "errors": [{"file": "", "line": None, "message": f"Path is not a directory: {project_directory}"}],
            "raw_output": "",
            "status": "❌ Invalid project directory"
        }
    
    try:
        # Run quickbuild -debug command
        process = subprocess.Popen(
            ["quickbuild", "-debug"],
            cwd=project_directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=True
        )
        
        # Wait for completion with timeout
        try:
            output, _ = process.communicate(timeout=timeout_minutes * 60)
            return_code = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            return {
                "success": False,
                "errors": [{"file": "", "line": None, "message": f"Build timed out after {timeout_minutes} minutes"}],
                "raw_output": "",
                "status": f"❌ Build timed out after {timeout_minutes} minutes"
            }
        
        # Parse the output for errors
        errors = _parse_build_errors(output)
        
        # Determine success based on return code and parsed errors
        success = return_code == 0 and len(errors) == 0
        
        if success:
            status = "✅ Build completed successfully - No errors found"
        else:
            error_count = len(errors)
            status = f"❌ Build failed with {error_count} error(s)"
        
        return {
            "success": success,
            "errors": [error.to_dict() for error in errors],
            "raw_output": output,
            "status": status
        }
        
    except FileNotFoundError:
        return {
            "success": False,
            "errors": [{"file": "", "line": None, "message": "quickbuild command not found. Ensure Azure QuickBuild tools are installed."}],
            "raw_output": "",
            "status": "❌ QuickBuild tool not found"
        }
    except Exception as e:
        return {
            "success": False,
            "errors": [{"file": "", "line": None, "message": f"Unexpected error: {str(e)}"}],
            "raw_output": "",
            "status": f"❌ Unexpected error: {str(e)}"
        }

def _parse_build_errors(build_output: str) -> List[QuickBuildError]:
    """
    Parse the build output to extract compilation errors.
    
    This function looks for common .NET compilation error patterns:
    - CS#### errors
    - File paths with line numbers
    - Error messages
    """
    errors = []
    
    # Common .NET error patterns
    patterns = [
        # Pattern: filepath(line,column): error CS####: message
        r'([^(]+)\((\d+),\d+\):\s*error\s+CS\d+:\s*(.+)',
        # Pattern: filepath(line): error CS####: message
        r'([^(]+)\((\d+)\):\s*error\s+CS\d+:\s*(.+)',
        # Pattern: error CS####: message
        r'error\s+CS\d+:\s*(.+)',
        # Pattern: filepath: error: message
        r'([^:]+):\s*error:\s*(.+)',
        # Pattern: Build FAILED
        r'Build FAILED\.\s*(.+)'
    ]
    
    lines = build_output.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                if len(match.groups()) >= 3:
                    # File path, line number, and message
                    file_path = match.group(1).strip()
                    try:
                        line_number = int(match.group(2))
                    except (ValueError, IndexError):
                        line_number = None
                    error_message = match.group(3).strip()
                elif len(match.groups()) == 2:
                    # File path and message, or just message with context
                    if ':' in match.group(1):
                        file_path = match.group(1).strip()
                        error_message = match.group(2).strip()
                        line_number = None
                    else:
                        file_path = ""
                        error_message = match.group(1).strip()
                        line_number = None
                else:
                    # Just the error message
                    file_path = ""
                    line_number = None
                    error_message = match.group(1).strip()
                
                errors.append(QuickBuildError(file_path, line_number, error_message))
                break
    
    # Additional parsing for MSBuild errors that might not match the patterns above
    if 'Build FAILED' in build_output and not errors:
        # If build failed but no specific errors were parsed, include general failure
        errors.append(QuickBuildError("", None, "Build failed - check raw output for details"))
    
    return errors

if __name__ == "__main__":
    mcp.run()