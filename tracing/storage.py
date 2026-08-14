import json
import sqlite3
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger("agent_orchestrator.tracing")

class TraceStorage:
    def __init__(self, db_url: str = "sqlite:///traces.db"):
        self.db_url = db_url
        self.is_postgres = False
        
        if self.db_url.startswith("postgresql://"):
            try:
                import psycopg2 # type: ignore
                self.is_postgres = True
                self.conn_str = self.db_url
            except ImportError:
                logger.warning("psycopg2 not installed. Falling back to SQLite.")
                self.db_url = "sqlite:///traces.db"
        
        if not self.is_postgres:
            if self.db_url.startswith("sqlite:///"):
                self.db_path = self.db_url.replace("sqlite:///", "")
            else:
                self.db_path = "traces.db"
                
        self._create_tables()

    def _get_connection(self):
        if self.is_postgres:
            import psycopg2 # type: ignore
            return psycopg2.connect(self.conn_str)
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

    def _create_tables(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if self.is_postgres:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS traces (
                            task_id TEXT PRIMARY KEY,
                            request TEXT,
                            trace_tree JSONB,
                            total_cost REAL,
                            total_latency_ms REAL,
                            total_tokens INT,
                            status TEXT,
                            created_at TIMESTAMP,
                            completed_at TIMESTAMP
                        )
                    """)
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS spans (
                            span_id TEXT PRIMARY KEY,
                            task_id TEXT,
                            node_name TEXT,
                            span_type TEXT,
                            parent_id TEXT,
                            input_tokens INT,
                            output_tokens INT,
                            cost REAL,
                            latency_ms REAL,
                            status TEXT,
                            metadata JSONB,
                            error TEXT,
                            prompt TEXT,
                            response TEXT
                        )
                    """)
                else:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS traces (
                            task_id TEXT PRIMARY KEY,
                            request TEXT,
                            trace_tree TEXT,
                            total_cost REAL,
                            total_latency_ms REAL,
                            total_tokens INT,
                            status TEXT,
                            created_at TEXT,
                            completed_at TEXT
                        )
                    """)
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS spans (
                            span_id TEXT PRIMARY KEY,
                            task_id TEXT,
                            node_name TEXT,
                            span_type TEXT,
                            parent_id TEXT,
                            input_tokens INT,
                            output_tokens INT,
                            cost REAL,
                            latency_ms REAL,
                            status TEXT,
                            metadata TEXT,
                            error TEXT,
                            prompt TEXT,
                            response TEXT
                        )
                    """)
                conn.commit()
        except Exception as e:
            logger.error(f"Error creating tables: {e}")

    def save_trace(self, task_id: str, request: str, trace_tree: dict,
                   total_cost: float, total_latency: float, total_tokens: int,
                   status: str = "completed") -> None:
        try:
            now = datetime.now().isoformat()
            tree_str = json.dumps(trace_tree)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if self.is_postgres:
                    cursor.execute("""
                        INSERT INTO traces (task_id, request, trace_tree, total_cost, total_latency_ms, total_tokens, status, created_at, completed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (task_id) DO UPDATE SET
                            request = EXCLUDED.request,
                            trace_tree = EXCLUDED.trace_tree,
                            total_cost = EXCLUDED.total_cost,
                            total_latency_ms = EXCLUDED.total_latency_ms,
                            total_tokens = EXCLUDED.total_tokens,
                            status = EXCLUDED.status,
                            completed_at = EXCLUDED.completed_at
                    """, (task_id, request, tree_str, total_cost, total_latency, total_tokens, status, now, now))
                else:
                    cursor.execute("""
                        INSERT OR REPLACE INTO traces (task_id, request, trace_tree, total_cost, total_latency_ms, total_tokens, status, created_at, completed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM traces WHERE task_id = ?), ?), ?)
                    """, (task_id, request, tree_str, total_cost, total_latency, total_tokens, status, task_id, now, now))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving trace: {e}")

    def save_spans(self, task_id: str, spans: List[dict]) -> None:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for span in spans:
                    meta_str = json.dumps(span.get("metadata", {}))
                    if self.is_postgres:
                        cursor.execute("""
                            INSERT INTO spans (span_id, task_id, node_name, span_type, parent_id, input_tokens, output_tokens, cost, latency_ms, status, metadata, error, prompt, response)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (span_id) DO UPDATE SET
                                status = EXCLUDED.status,
                                metadata = EXCLUDED.metadata,
                                error = EXCLUDED.error
                        """, (
                            span.get("span_id"), task_id, span.get("node_name"), span.get("span_type"),
                            span.get("parent_id"), span.get("input_tokens", 0), span.get("output_tokens", 0),
                            span.get("cost_usd", 0.0), span.get("latency_ms", 0.0), span.get("status"),
                            meta_str, span.get("error"), span.get("prompt"), span.get("response")
                        ))
                    else:
                        cursor.execute("""
                            INSERT OR REPLACE INTO spans (span_id, task_id, node_name, span_type, parent_id, input_tokens, output_tokens, cost, latency_ms, status, metadata, error, prompt, response)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            span.get("span_id"), task_id, span.get("node_name"), span.get("span_type"),
                            span.get("parent_id"), span.get("input_tokens", 0), span.get("output_tokens", 0),
                            span.get("cost_usd", 0.0), span.get("latency_ms", 0.0), span.get("status"),
                            meta_str, span.get("error"), span.get("prompt"), span.get("response")
                        ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving spans: {e}")

    def get_trace(self, task_id: str) -> Optional[dict]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM traces WHERE task_id = %s" if self.is_postgres else "SELECT * FROM traces WHERE task_id = ?"
                cursor.execute(query, (task_id,))
                row = cursor.fetchone()
                if row:
                    data = dict(row) if not self.is_postgres else {desc[0]: val for desc, val in zip(cursor.description, row)}
                    if isinstance(data.get("trace_tree"), str):
                        data["trace_tree"] = json.loads(data["trace_tree"])
                    return data
        except Exception as e:
            logger.error(f"Error getting trace: {e}")
        return None

    def get_span(self, span_id: str) -> Optional[dict]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM spans WHERE span_id = %s" if self.is_postgres else "SELECT * FROM spans WHERE span_id = ?"
                cursor.execute(query, (span_id,))
                row = cursor.fetchone()
                if row:
                    data = dict(row) if not self.is_postgres else {desc[0]: val for desc, val in zip(cursor.description, row)}
                    if isinstance(data.get("metadata"), str):
                        data["metadata"] = json.loads(data["metadata"])
                    return data
        except Exception as e:
            logger.error(f"Error getting span: {e}")
        return None

    def list_traces(self, limit: int = 50, offset: int = 0) -> List[dict]:
        traces = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT task_id, request, total_cost, total_latency_ms, total_tokens, status, created_at FROM traces ORDER BY created_at DESC LIMIT %s OFFSET %s" if self.is_postgres else "SELECT task_id, request, total_cost, total_latency_ms, total_tokens, status, created_at FROM traces ORDER BY created_at DESC LIMIT ? OFFSET ?"
                cursor.execute(query, (limit, offset))
                rows = cursor.fetchall()
                for row in rows:
                    data = dict(row) if not self.is_postgres else {desc[0]: val for desc, val in zip(cursor.description, row)}
                    traces.append(data)
        except Exception as e:
            logger.error(f"Error listing traces: {e}")
        return traces

    def search_traces(self, query: str = None, min_cost: float = None, status: str = None) -> List[dict]:
        traces = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                conditions = []
                params = []
                if query:
                    conditions.append("request LIKE %s" if self.is_postgres else "request LIKE ?")
                    params.append(f"%{query}%")
                if min_cost is not None:
                    conditions.append("total_cost >= %s" if self.is_postgres else "total_cost >= ?")
                    params.append(min_cost)
                if status:
                    conditions.append("status = %s" if self.is_postgres else "status = ?")
                    params.append(status)
                
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                sql = f"SELECT task_id, request, total_cost, total_latency_ms, total_tokens, status, created_at FROM traces WHERE {where_clause} ORDER BY created_at DESC"
                
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                for row in rows:
                    data = dict(row) if not self.is_postgres else {desc[0]: val for desc, val in zip(cursor.description, row)}
                    traces.append(data)
        except Exception as e:
            logger.error(f"Error searching traces: {e}")
        return traces

    def get_cost_analytics(self, days: int = 30) -> dict:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if self.is_postgres:
                    cursor.execute("""
                        SELECT COUNT(*) as total_tasks, SUM(total_cost) as total_cost, AVG(total_cost) as avg_cost, SUM(total_tokens) as total_tokens
                        FROM traces WHERE created_at >= NOW() - INTERVAL '%s days'
                    """, (days,))
                else:
                    cursor.execute("""
                        SELECT COUNT(*) as total_tasks, SUM(total_cost) as total_cost, AVG(total_cost) as avg_cost, SUM(total_tokens) as total_tokens
                        FROM traces WHERE created_at >= date('now', ?)
                    """, (f"-{days} days",))
                row = cursor.fetchone()
                if row:
                    data = dict(row) if not self.is_postgres else {desc[0]: val for desc, val in zip(cursor.description, row)}
                    return {k: (v or 0) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error getting analytics: {e}")
        return {"total_tasks": 0, "total_cost": 0.0, "avg_cost": 0.0, "total_tokens": 0}

    def delete_trace(self, task_id: str) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                q1 = "DELETE FROM spans WHERE task_id = %s" if self.is_postgres else "DELETE FROM spans WHERE task_id = ?"
                q2 = "DELETE FROM traces WHERE task_id = %s" if self.is_postgres else "DELETE FROM traces WHERE task_id = ?"
                cursor.execute(q1, (task_id,))
                cursor.execute(q2, (task_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting trace: {e}")
            return False
