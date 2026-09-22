import os

import duckdb
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

_STATS_DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'f1_stats.db')

class VerificationResult(BaseModel):
    is_safe: bool = Field(description="True if the query only uses SELECT and targets allowed tables. Must be False if it contains DROP, DELETE, INSERT, UPDATE, or PRAGMA.")
    reason: str = Field(description="Explanation of why the query is safe or rejected.")

def _get_schema_context(con: duckdb.DuckDBPyConnection) -> str:
    tables = ["drivers", "constructors", "circuits", "races", "results"]
    context_lines = []
    
    for table in tables:
        # Get schema
        schema_rows = con.execute(f"DESCRIBE {table}").fetchall()
        schema_str = ", ".join([f"{row[0]} ({row[1]})" for row in schema_rows])
        context_lines.append(f"Table '{table}': {schema_str}")
        
        # Get 2 sample rows
        sample_rows = con.execute(f"SELECT * FROM {table} LIMIT 2").fetchall()
        context_lines.append(f"  Sample data: {sample_rows}")
        
    return "\n".join(context_lines)

def run_sql_query(question: str) -> str:
    """End-to-end pipeline to generate, verify, and execute SQL against F1 stats."""
    
    if not os.path.exists(_STATS_DB_PATH):
        return "Database not found. Please run seed script first."
        
    # We connect with read_only=True at the driver level for ultimate safety
    con = duckdb.connect(_STATS_DB_PATH, read_only=True)
    try:
        # 1. Gather Context
        schema_context = _get_schema_context(con)
        
        # 2. SQL Agent (Generator)
        generator_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        gen_prompt = (
            f"You are a DuckDB SQL expert. Write a query to answer the following question.\n\n"
            f"Schema and Samples:\n{schema_context}\n\n"
            f"Question: {question}\n\n"
            f"Return ONLY the raw SQL query. Do not wrap in markdown tags like ```sql. "
            f"Ensure you handle joins correctly. Do not try to attach databases, just query the tables directly."
        )
        sql_raw = generator_llm.invoke([("user", gen_prompt)]).content
        sql = sql_raw.replace('```sql', '').replace('```', '').strip()
        
        # 3. Verifier Agent
        verifier_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0).with_structured_output(VerificationResult)
        verify_prompt = (
            f"Review this DuckDB SQL query: {sql}\n\n"
            f"Is it a safe, read-only SELECT query? Reject anything that modifies data, drops tables, or alters settings."
        )
        verification = verifier_llm.invoke([("user", verify_prompt)])
        
        if not getattr(verification, "is_safe", False):
            return f"Query rejected by Verifier Agent: {getattr(verification, 'reason', 'Unknown reason')}"
            
        # 4. Execution Engine
        res = con.execute(sql).fetchall()
        columns = [desc[0] for desc in con.description]
        
        # 5. Format Return Data
        if not res:
            return "Query executed successfully but returned no results."
            
        # Limit rows returned to LLM to prevent context overflow
        MAX_ROWS = 20
        res_str_lines = [f"Columns: {', '.join(columns)}"]
        for row in res[:MAX_ROWS]:
            res_str_lines.append(str(row))
            
        if len(res) > MAX_ROWS:
            res_str_lines.append(f"... and {len(res) - MAX_ROWS} more rows.")
            
        return "\n".join(res_str_lines)
        
    except Exception as e:
        return f"Error executing SQL sub-agent pipeline: {str(e)}"
    finally:
        con.close()

