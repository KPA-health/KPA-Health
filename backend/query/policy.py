import sqlglot
import sqlglot.expressions as exp
import logging

# Vistas permitidas
ALLOWED_TABLES = {
    "v_admissions_daily", 
    "v_wait_daily", 
    "v_triage_daily", 
    "v_medication_daily", 
    "v_services_daily"
}

def validate_sql(sql: str) -> bool:
    try:
        # Check for multiple statements
        statements = sqlglot.parse(sql, read="sqlite")
        if len(statements) != 1:
            logging.error("Multiple statements are not allowed.")
            return False
            
        stmt = statements[0]
        
        # Only allow SELECT
        if not isinstance(stmt, exp.Select):
            logging.error("Only SELECT statements are allowed.")
            return False

        # Reject JOIN, CTE (With), UNION, Subqueries in unexpected places
        for node in stmt.find_all(exp.Join):
            logging.error("JOIN is not allowed.")
            return False
        if stmt.args.get("with"):
            logging.error("CTE (WITH) is not allowed.")
            return False
        for node in stmt.find_all(exp.Union):
            logging.error("UNION is not allowed.")
            return False

        # Ensure only allowed tables are accessed
        for table in stmt.find_all(exp.Table):
            table_name = table.name.lower()
            if table_name not in ALLOWED_TABLES:
                logging.error(f"Table {table_name} is not allowed.")
                return False
                
        # Reject DDL/DML, PRAGMA by structure, but sqlglot parse should catch non-Selects.
        return True

    except Exception as e:
        logging.error(f"SQL validation error: {e}")
        return False
