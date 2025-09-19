# Azure .NET QuickBuild MCP Server

This Model Context Protocol (MCP) server provides integration with Azure .NET QuickBuild for testing project compilation from Copilot CLI.

## Overview

The server exposes a single tool `azure_net_quickbuild` that:
- Runs `quickbuild -debug` in a specified project directory
- Captures and parses compilation output 
- Returns structured results indicating success/failure
- Extracts error details with file locations and line numbers
- Provides clear status messages for Copilot CLI

## Tool: `azure_net_quickbuild`

### Parameters

- `project_directory` (required): Absolute path to the directory containing the .NET project
- `timeout_minutes` (optional): Maximum time to wait for build completion (default: 10 minutes)

### Returns

```json
{
  "success": boolean,
  "errors": [
    {
      "file": "string",
      "line": number | null,
      "message": "string"
    }
  ],
  "raw_output": "string",
  "status": "string"
}
```

### Response Format

#### Success Response
```json
{
  "success": true,
  "errors": [],
  "raw_output": "...",
  "status": "✅ Build completed successfully - No errors found"
}
```

#### Error Response
```json
{
  "success": false,
  "errors": [
    {
      "file": "MyProject.cs",
      "line": 15,
      "message": "The name 'invalidVariable' does not exist in the current context"
    }
  ],
  "raw_output": "...",
  "status": "❌ Build failed with 1 error(s)"
}
```

## Error Parsing

The server intelligently parses various .NET compilation error formats:

- `filepath(line,column): error CS####: message`
- `filepath(line): error CS####: message`  
- `error CS####: message`
- `filepath: error: message`
- `Build FAILED` messages

## Usage with Copilot CLI

When Copilot CLI needs to test if a .NET project compiles, it can call this tool:

```json
{
  "tool": "azure_net_quickbuild",
  "arguments": {
    "project_directory": "/path/to/your/dotnet/project",
    "timeout_minutes": 5
  }
}
```

The tool will:
1. Validate the project directory exists
2. Run `quickbuild -debug` in that directory
3. Wait for completion (up to timeout)
4. Parse output for compilation errors
5. Return structured results

## Prerequisites

- Azure QuickBuild tools must be installed and available in PATH
- `quickbuild` command must be accessible from the target project directory
- Project directory must contain a valid .NET project structure

## Error Handling

The server handles various error conditions:

- **Directory not found**: Returns error if project directory doesn't exist
- **Invalid directory**: Returns error if path is not a directory
- **Command not found**: Returns error if `quickbuild` is not installed
- **Timeout**: Kills process and returns timeout error if build takes too long
- **Unexpected errors**: Catches and reports any other exceptions

## Testing

Run the test suite to verify functionality:

```bash
cd mcp_servers/azure-net-quickbuild/src
python test_server.py
```

## Server Startup

To run the MCP server:

```bash
cd mcp_servers/azure-net-quickbuild/src
python server.py
```

The server will start in STDIO mode and wait for MCP client connections.