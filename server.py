import os
import sqlite3
import sys
import glob
import shutil
from pathlib import Path

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastmcp import FastMCP, Context

class AppContext:
    dbconn: sqlite3.Connection
    
    def __init__(self, dbconn: sqlite3.Connection):
        self.dbconn = dbconn

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Create necessary view in the database"""
    # Initialize on startup
    
    try:
        # Find the latest .mmbak file in Downloads directory
        home_dir = os.path.expanduser("~")
        download_dir = os.path.join(home_dir, "Downloads")
        mmbak_files = glob.glob(os.path.join(download_dir, "*.mmbak"))
        
        if not mmbak_files:
            print("Error: No .mmbak files found in Downloads directory.", file=sys.stderr)
            sys.exit(1)  # Exit with error code 1
        
        # Sort by creation time (newest first)
        latest_mmbak = max(mmbak_files, key=os.path.getctime)
        print(f"Using latest backup file: {latest_mmbak}", file=sys.stderr)
        
        # Copy to current directory as piggy.sqlite
        shutil.copy2(latest_mmbak, "./piggy.sqlite")
        print(f"Copied {latest_mmbak} to ./piggy.sqlite", file=sys.stderr)
        
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

    1. Almost everything you need are in the `expenses` view. It has these columns:
            - ZTXDATESTR: The transaction date string in ISO8601
            - TXN_YEAR: The transaction year (good for GROUP BY)
            - ZCONTENT: The transaction recipient or description
            - SPENT_MYR: The amount spent in Malaysian Ringgit
            - DEST_CURRENCY: The destination currency code
            - PARENT_CATEGORY_NAME: The parent category name
            - CATEGORY_NAME: The subcategory name

    2. It is advisable to discover all the categories & parent categories before searching for transactions.
            `SELECT DISTINCT PARENT_CATEGORY_NAME FROM expenses;`
            `SELECT DISTINCT CATEGORY_NAME FROM expenses;`

    3. Some merchants are the same, but slightly different ZCONTENT may be used. For example:
            - Zus Coffee / Zus Delivery

    4. It is possible to recreate a trip itinerary from MIN/MAX(ZTXDATESTR) and DEST_CURRENCY for every year.
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

if __name__ == "__main__":
    mcp.run()
