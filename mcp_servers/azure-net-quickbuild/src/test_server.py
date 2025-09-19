#!/usr/bin/env python3
"""
Test script for Azure .NET QuickBuild MCP server functionality.
This script tests the core logic without requiring MCP client infrastructure.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the raw function before it gets decorated
import subprocess
import re
from typing import Dict, List, Optional

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

def azure_net_quickbuild_raw(project_directory: str, timeout_minutes: int = 10) -> Dict:
    """Raw version of the function for testing purposes."""
    
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
    """Parse the build output to extract compilation errors."""
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

def test_azure_net_quickbuild():
    """Test the azure_net_quickbuild function with different scenarios."""
    
    print("🧪 Testing Azure .NET QuickBuild MCP Server")
    print("=" * 50)
    
    # Test 1: Invalid directory
    print("\n📋 Test 1: Invalid directory")
    result = azure_net_quickbuild_raw("/nonexistent/directory")
    print(f"Success: {result['success']}")
    print(f"Status: {result['status']}")
    print(f"Errors: {len(result['errors'])}")
    assert not result['success'], "Should fail for nonexistent directory"
    
    # Test 2: Current directory (should exist but may not have quickbuild)
    print("\n📋 Test 2: Current directory (expecting quickbuild command not found)")
    current_dir = os.getcwd()
    result = azure_net_quickbuild_raw(current_dir, timeout_minutes=1)
    print(f"Success: {result['success']}")
    print(f"Status: {result['status']}")
    print(f"Errors: {len(result['errors'])}")
    if result['errors']:
        print(f"First error: {result['errors'][0]['message']}")
    
    # Test 3: Test error parsing function
    print("\n📋 Test 3: Error parsing functionality")
    
    sample_output = """
Microsoft (R) Build Engine version 17.0.0+c9eb9dd64 for .NET
Copyright (C) Microsoft Corporation. All rights reserved.

  Determining projects to restore...
  All projects are up-to-date for restore.
MyProject.cs(15,5): error CS0103: The name 'invalidVariable' does not exist in the current context
AnotherFile.cs(23): error CS1002: ; expected
  Build FAILED.
      0 Warning(s)
      2 Error(s)
"""
    
    errors = _parse_build_errors(sample_output)
    print(f"Parsed {len(errors)} errors:")
    for i, error in enumerate(errors, 1):
        print(f"  {i}. File: {error.file_path}, Line: {error.line_number}, Message: {error.error_message}")
    
    assert len(errors) >= 2, "Should parse at least 2 errors from sample output"
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_azure_net_quickbuild()