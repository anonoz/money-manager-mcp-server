# Piggy MCP Server

Allows talking to Money Manager database.

To begin, export mmbak file and place it in this directory as piggy.sqlite file.

This project forks from sqlite reference mcp server.

## Setup

Install dependencies

```
git clone
uv sync
```

Start the inspector

```
uv run mcp dev server.py
```


Add it to Claude Desktop

```
uv run mcp install server.py
```
