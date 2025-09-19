# Copilot-Cli-MCP-Tools

A collection of Model Context Protocol (MCP) servers designed to enhance the GitHub Copilot CLI experience with additional tools and capabilities.

## Overview

This project provides MCP servers that extend the functionality of GitHub Copilot CLI by offering custom tools and integrations. The Model Context Protocol enables AI assistants to securely connect with external data sources and tools.

## Project Structure

```
Copilot-Cli-MCP-Tools/
├── mcp_servers/           # Collection of MCP server implementations
│   └── boilerplate/       # Basic MCP server template
│       └── src/
│           └── server.py  # Simple greeting tool server
├── requirements.txt       # Python dependencies
├── venv/                 # Python virtual environment
└── README.md            # This file
```

## Prerequisites

- Python 3.13+ (tested with Python 3.13.3)
- GitHub Copilot CLI
- Git

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/Copilot-Cli-MCP-Tools.git
   cd Copilot-Cli-MCP-Tools
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## MCP Servers

### Boilerplate Server

A simple example MCP server that demonstrates the basic structure and functionality.

**Features:**
- `greet(name)` tool - Returns a personalized greeting

**Usage:**
```bash
cd mcp_servers/boilerplate/src
python server.py
```

## Key Dependencies

- **fastmcp (2.12.3)** - Framework for building MCP servers
- **mcp (1.14.1)** - Core MCP protocol implementation
- **pydantic (2.11.9)** - Data validation and parsing
- **httpx (0.28.1)** - HTTP client for API integrations
- **rich (14.1.0)** - Rich text and formatting
- **uvicorn (0.35.0)** - ASGI server implementation

## Development

### Adding New MCP Servers

1. Create a new directory under `mcp_servers/`:
   ```bash
   mkdir mcp_servers/your-server-name
   cd mcp_servers/your-server-name
   mkdir src
   ```

2. Create your server implementation in `src/server.py`:
   ```python
   from fastmcp import FastMCP

   mcp = FastMCP("Your Server Name")

   @mcp.tool
   def your_tool(param: str) -> str:
       return f"Result: {param}"

   if __name__ == "__main__":
       mcp.run()
   ```

3. Test your server:
   ```bash
   python src/server.py
   ```

### Project Standards

- Use Python 3.13+
- Follow the FastMCP framework patterns
- Include type hints for all functions
- Document tools with clear descriptions
- Keep servers focused on specific functionality

## Integration with GitHub Copilot CLI

Once your MCP servers are running, they can be connected to GitHub Copilot CLI to provide additional tools and capabilities during your development workflow.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes and test thoroughly
4. Commit your changes: `git commit -am 'Add your feature'`
5. Push to the branch: `git push origin feature/your-feature-name`
6. Submit a pull request

## License

This project is open source. Please check the LICENSE file for details.

## Roadmap

- [ ] Add file system operations MCP server
- [ ] Add API integration MCP server
- [ ] Add database query MCP server
- [ ] Add code analysis MCP server
- [ ] Add deployment tools MCP server
- [ ] Documentation and examples for each server
- [ ] Integration tests
- [ ] Docker containerization

## Resources

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [GitHub Copilot CLI Documentation](https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-in-the-command-line)