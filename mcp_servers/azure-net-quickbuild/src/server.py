import asyncio
import subprocess
import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from fastmcp import FastMCP

mcp = FastMCP("Azure Net Quickbuild MCP Server")

# Check if logging is enabled via environment variable
LOGGING_ENABLED = os.getenv("ENABLE_QUICKBUILD_MCP_LOGS", "").lower() in ("true", "1", "yes", "on")

# Set up logging only if enabled
if LOGGING_ENABLED:
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "quickbuild_usage.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Also log to console for debugging
        ]
    )
    logger = logging.getLogger(__name__)
else:
    # Create a no-op logger when logging is disabled
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.NullHandler())
    logger.setLevel(logging.CRITICAL + 1)  # Disable all logging

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

def _log_build_result(project_directory: str, result: Dict, raw_output: str, build_mode: str = "unknown") -> None:
    """
    Log build result details to file for tracking and debugging.
    Only logs if ENABLE_QUICKBUILD_MCP_LOGS environment variable is set.
    """
    if not LOGGING_ENABLED:
        return  # Skip all logging if disabled
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "project_directory": project_directory,
        "build_mode": build_mode,
        "success": result["success"],
        "error_count": len(result["errors"]),
        "errors": result["errors"],
        "status": result["status"],
        "full_console_output": raw_output  # Store complete output for troubleshooting
    }
    
    logger.info(f"QuickBuild executed for {project_directory} (mode: {build_mode})")
    logger.info(f"Result: {result['status']}")
    if result["errors"]:
        logger.info(f"Errors found ({len(result['errors'])}):")
        for i, error in enumerate(result["errors"], 1):
            logger.info(f"  {i}. {error['file']}:{error['line']} - {error['message']}")
    
    # Log a preview of the console output to the main log
    if raw_output:
        preview = raw_output[:300] + "..." if len(raw_output) > 300 else raw_output
        logger.info(f"Console output preview: {preview}")
    
    # Write detailed JSON log with full console output
    json_log_file = os.path.join(os.path.dirname(log_file), "quickbuild_detailed.jsonl")
    try:
        with open(json_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        logger.info(f"Full console output logged to: {json_log_file}")
    except Exception as e:
        logger.error(f"Failed to write detailed log: {e}")
    
    # Also create a separate readable console output log
    console_log_file = os.path.join(os.path.dirname(log_file), "console_output.log")
    try:
        with open(console_log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"TIMESTAMP: {datetime.now().isoformat()}\n")
            f.write(f"PROJECT: {project_directory}\n")
            f.write(f"BUILD MODE: {build_mode}\n")
            f.write(f"STATUS: {result['status']}\n")
            f.write(f"{'='*80}\n")
            f.write(raw_output)
            f.write(f"\n{'='*80}\n\n")
        logger.info(f"Readable console output logged to: {console_log_file}")
    except Exception as e:
        logger.error(f"Failed to write console output log: {e}")

@mcp.tool
def azure_net_quickbuild(
    project_directory: str,
    timeout_minutes: int = 10,
    build_mode: str = "debug"
) -> Dict:
    """
    Runs Azure .NET QuickBuild with various options to test project compilation.
    
    Args:
        project_directory: The absolute path to the directory containing the .NET project
        timeout_minutes: Maximum time to wait for build completion (default: 10 minutes)
        build_mode: Build mode - "debug" (quickbuild -debug), "notest" (quickbuild -notest -debug), or "standard" (quickbuild)
    
    Returns:
        Dict containing:
        - success: bool indicating if build succeeded
        - errors: List of error objects with file, line, and message
        - error_output: Only the error-relevant lines from build output
        - status: Human-readable status message
    """
    
    # Validate directory exists
    if not os.path.exists(project_directory):
        if LOGGING_ENABLED:
            logger.warning(f"QuickBuild failed: Project directory not found - {project_directory}")
        return {
            "success": False,
            "errors": [{"file": "", "line": None, "message": f"Project directory not found: {project_directory}"}],
            "error_output": "",
            "status": "❌ Project directory not found"
        }
    
    # Validate directory is accessible
    if not os.path.isdir(project_directory):
        if LOGGING_ENABLED:
            logger.warning(f"QuickBuild failed: Invalid project directory - {project_directory}")
        return {
            "success": False,
            "errors": [{"file": "", "line": None, "message": f"Path is not a directory: {project_directory}"}],
            "error_output": "",
            "status": "❌ Invalid project directory"
        }
    
    try:
        # Determine quickbuild command based on build_mode
        if build_mode == "debug":
            command = ["quickbuild", "-debug"]
        elif build_mode == "notest":
            command = ["quickbuild", "-notest", "-debug"]
        elif build_mode == "standard":
            command = ["quickbuild"]
        else:
            if LOGGING_ENABLED:
                logger.error(f"Invalid build_mode '{build_mode}' for {project_directory}")
            return {
                "success": False,
                "errors": [{"file": "", "line": None, "message": f"Invalid build_mode: {build_mode}. Use 'debug', 'notest', or 'standard'"}],
                "error_output": "",
                "status": "❌ Invalid build mode"
            }
        
        if LOGGING_ENABLED:
            logger.info(f"Running command: {' '.join(command)} in {project_directory}")
        
        # Run quickbuild command
        process = subprocess.Popen(
            command,
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
            if LOGGING_ENABLED:
                logger.warning(f"QuickBuild timed out after {timeout_minutes} minutes for {project_directory}")
            return {
                "success": False,
                "errors": [{"file": "", "line": None, "message": f"Build timed out after {timeout_minutes} minutes"}],
                "error_output": "",
                "status": f"❌ Build timed out after {timeout_minutes} minutes"
            }
        
        # Parse the output for errors
        errors = _parse_build_errors(output)
        
        # Extract only error-relevant lines from the output
        error_output = _extract_error_lines(output)
        
        # Determine success based on return code and parsed errors
        success = return_code == 0 and len(errors) == 0
        
        if success:
            status = "✅ Build completed successfully - No errors found"
        else:
            error_count = len(errors)
            status = f"❌ Build failed with {error_count} error(s)"
        
        result = {
            "success": success,
            "errors": [error.to_dict() for error in errors],
            "error_output": error_output,
            "status": status
        }
        
        # Log the build result
        _log_build_result(project_directory, result, output, build_mode)
        
        return result
        
    except FileNotFoundError:
        if LOGGING_ENABLED:
            logger.error(f"QuickBuild command not found for project {project_directory}")
        return {
            "success": False,
            "errors": [{"file": "", "line": None, "message": "quickbuild command not found. Ensure Azure QuickBuild tools are installed."}],
            "error_output": "",
            "status": "❌ QuickBuild tool not found"
        }
    except Exception as e:
        if LOGGING_ENABLED:
            logger.error(f"Unexpected error during QuickBuild for {project_directory}: {str(e)}")
        return {
            "success": False,
            "errors": [{"file": "", "line": None, "message": f"Unexpected error: {str(e)}"}],
            "error_output": "",
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

def _extract_error_lines(build_output: str) -> str:
    """
    Extract only error-relevant lines from the build output to reduce token usage.
    
    This function filters the build output to include only:
    - Lines containing .NET compilation errors (CS####)
    - Lines containing the word "error" (case insensitive)
    - Build failure summary lines
    - Lines with file paths that have errors
    """
    if not build_output.strip():
        return ""
    
    error_lines = []
    lines = build_output.split('\n')
    
    # Patterns that indicate error-relevant lines
    error_indicators = [
        r'error\s+CS\d+',  # CS#### errors
        r'\berror\b',       # General errors (case insensitive via flags)
        r'Build FAILED',    # Build failure
        r'Build failed',    # Build failure (alternate)
        r'\(\d+,\d+\):\s*error',  # File(line,col): error
        r'\(\d+\):\s*error',      # File(line): error
        r'MSB\d+',         # MSBuild errors
        r'fatal error',    # Fatal errors
    ]
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        # Check if line matches any error pattern
        for pattern in error_indicators:
            if re.search(pattern, line, re.IGNORECASE):
                error_lines.append(line)
                break
    
    # If we found no error lines but the build output exists, include a summary
    if not error_lines and build_output.strip():
        # Look for build result summary
        for line in lines:
            if any(keyword in line.lower() for keyword in ['failed', 'succeeded', 'build']):
                if any(keyword in line.lower() for keyword in ['failed', 'error']):
                    error_lines.append(line)
    
    return '\n'.join(error_lines) if error_lines else "No specific error details found in build output"

if __name__ == "__main__":
    mcp.run()