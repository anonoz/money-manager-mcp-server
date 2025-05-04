import os
import sqlite3
import sys

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP, Context

class AppContext:
    dbconn: sqlite3.Connection
    
    def __init__(self, dbconn: sqlite3.Connection):
        self.dbconn = dbconn

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Create necessary view in the database"""
    # Initialize on startup
    
    try:
        # Check if database file exists
        if not os.path.exists("./piggy.sqlite"):
            print("Error: piggy.sqlite does not exist.", file=sys.stderr)
            sys.exit(1)  # Exit with error code 1
            
        dbconn = sqlite3.connect("./piggy.sqlite")
        with open("./sqls/expenses.view.sql", "r") as sql_file:
            sql_script = sql_file.read()
        dbconn.executescript(sql_script)
        dbconn.commit()
        print("Expenses view created successfully", file=sys.stderr)

        # ctx = AppContext(dbconn=dbconn)
        yield AppContext(dbconn=dbconn)
    finally:
        # Cleanup on shutdown
        if 'dbconn' in locals():
            dbconn.close()

mcp = FastMCP("Piggy Explorer", lifespan=app_lifespan)

@mcp.resource("intro://readme")
def general_introduction() -> str:
    """Explain to MCP Client how to work with this server"""
    return """
    This MCP server allows reading of a sqlite database exported from Money Manager - a personal finance app.

    1. For most cases, one only needs to read from the expenses view.
    2. Do your best to avoid reading from other tables with prefix Z.
    """

# @mcp.resource("schema://all")
# def get_all_schema() -> str:
#     """Provide the database schema as a resource"""
#     ctx = mcp.get_context()
#     schema = ctx.request_context.lifespan_context.dbconn.execute("SELECT sql FROM sqlite_master WHERE type='table'").fetchall()
#     return "\n".join(sql[0] for sql in schema if sql[0])
                     
@mcp.resource("schema://explain-expenses-view")
def get_expenses_schema() -> str:
    """The main view that client should query"""
    ctx = mcp.get_context()
    schema_str = ctx.request_context.lifespan_context.dbconn.execute("SELECT sql FROM sqlite_master WHERE name='expenses';").fetchone()
    return f"""
    The DML of expenses view:
    {schema_str}
    """

@mcp.tool()
def query_data(sql: str) -> str:
    """
    Execute SELECT SQLs safely.

    To 
    """
    ctx = mcp.get_context()
    # Check if query contains write operations
    sql_lower = sql.lower()
    forbidden_keywords = ['insert', 'update', 'delete', 'drop', 'alter', 'create', 'pragma', 'attach']
    if any(keyword in sql_lower for keyword in forbidden_keywords):
        return "Error: Only SELECT queries are allowed"
    
    try:
        result = ctx.request_context.lifespan_context.dbconn.execute(sql).fetchall()
        return "\n".join(str(row) for row in result)
    except Exception as e:
        return f"Error: {str(e)}"
