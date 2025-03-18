#!/usr/bin/env python3
"""
RhinoMCP - Main entry point

This script serves as a convenience wrapper to start the RhinoMCP server.
"""

from rhino_mcp.server import main as server_main

def main():
    """Entry point for the rhino-mcp package"""
    server_main()

if __name__ == "__main__":
    main() 