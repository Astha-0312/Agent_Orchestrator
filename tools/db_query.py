import sqlite3
from .registry import default_registry

def is_select_query(query: str) -> bool:
    query = query.strip().lower()
    return query.startswith("select") or query.startswith("pragma") or query.startswith("explain")

def db_query(query: str, db_url: str = None) -> str:
    """Executes a read-only SQL query."""
    if not is_select_query(query):
        return "Error: Only read-only (SELECT) queries are allowed."
    
    if db_url is None:
        db_url = ":memory:"
    
    if db_url.startswith("postgres://") or db_url.startswith("postgresql://"):
        try:
            import psycopg2
        except ImportError:
            return "Error: psycopg2 module not installed for PostgreSQL queries."
        
        try:
            conn = psycopg2.connect(db_url, connect_timeout=10)
            conn.set_session(readonly=True)
            cur = conn.cursor()
            cur.execute(query)
            
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description] if cur.description else []
            conn.close()
            
            return format_table(cols, rows)
            
        except Exception as e:
            return f"Error executing PostgreSQL query: {str(e)}"
            
    else:
        try:
            conn = sqlite3.connect(db_url, timeout=10.0)
            cur = conn.cursor()
            cur.execute(query)
            
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description] if cur.description else []
            conn.close()
            
            return format_table(cols, rows)
            
        except Exception as e:
            return f"Error executing SQLite query: {str(e)}"

def format_table(cols, rows) -> str:
    if not cols and not rows:
        return "No results."
    
    rows = [[str(item) for item in row] for row in rows]
    cols = [str(col) for col in cols]
    
    col_widths = [len(col) for col in cols]
    for row in rows:
        for i, item in enumerate(row):
            if len(item) > col_widths[i]:
                col_widths[i] = len(item)
    
    header = " | ".join(col.ljust(width) for col, width in zip(cols, col_widths))
    separator = "-+-".join("-" * width for width in col_widths)
    
    lines = [header, separator]
    for row in rows:
        lines.append(" | ".join(item.ljust(width) for item, width in zip(row, col_widths)))
        
    return "\n".join(lines)

default_registry.register("db_query", db_query, "Execute read-only SQL query against a database.", {"query": "string", "db_url": "string (optional)"})
