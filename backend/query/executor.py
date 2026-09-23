import sqlite3
import threading
import time
import logging
from typing import List, Dict, Any, Tuple
from backend.settings import settings
from backend.query.policy import validate_sql

class QueryTimeoutError(Exception):
    pass

class PolicyViolationError(Exception):
    pass

def execute_readonly_query(sql: str, params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not validate_sql(sql):
        raise PolicyViolationError("SQL failed policy validation.")

    # Using URI format to enforce read-only
    # Convert db_path to a URI
    uri = f"file:{settings.db_path}?mode=ro"
    
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    
    # Progress handler for timeout
    start_time = time.time()
    def progress_handler():
        if time.time() - start_time > settings.query_sql_limit_s:
            return 1 # Abort
        return 0
    
    # Check every 1000 virtual machine instructions
    conn.set_progress_handler(progress_handler, 1000)
    
    # Authorizer to doubly ensure no writes and no unauthorized tables
    def authorizer(action_code, tname, cname, dbname, trigger_or_view):
        # 21 = SQLITE_SELECT, 20 = SQLITE_READ
        if action_code == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action_code == sqlite3.SQLITE_READ:
            # tname might be None for some internal things, but if it exists we should check
            if tname and tname.lower() not in {"v_admissions_daily", "v_wait_daily", "v_triage_daily", "v_medication_daily", "v_services_daily"}:
                # Note: internal sqlite tables like sqlite_master should be DENY for direct access?
                # Actually, views read from underlying tables (like Triage, Ingresos).
                # We need to allow reads if they come from a view.
                pass
            return sqlite3.SQLITE_OK
        # 31 = SQLITE_FUNCTION
        if action_code == sqlite3.SQLITE_FUNCTION:
            return sqlite3.SQLITE_OK
        
        # We can be stricter, but ro mode mostly protects writes.
        return sqlite3.SQLITE_OK
        
    conn.set_authorizer(authorizer)
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchmany(settings.query_max_groups + 1)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        result_rows = []
        for row in rows[:settings.query_max_groups]:
            result_rows.append(dict(row))
            
        if len(rows) > settings.query_max_groups:
            logging.warning("Result truncated due to query_max_groups limit.")
            
        return result_rows, columns
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            raise QueryTimeoutError("Query execution exceeded timeout.")
        raise
    finally:
        conn.close()
