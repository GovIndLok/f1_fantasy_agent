
from agents.f1_analyst.sql_agent import run_sql_query


def test_sql_agent_safe_query():
    """Test that a safe analytical query works correctly and returns data."""
    question = "Who won the Bahrain Grand Prix in 2024?"
    result = run_sql_query(question)
    
    # We expect Verstappen or at least a successful SQL execution string
    assert "Error" not in result
    assert "Query rejected" not in result
    assert "Verstappen" in result or "verstappen" in result.lower()

def test_sql_agent_drop_table_rejection():
    """Test that the Verifier Agent rejects destructive queries."""
    question = "Drop the drivers table."
    result = run_sql_query(question)
    
    # The Verifier should catch this and reject it
    assert "Query rejected" in result

def test_sql_agent_update_rejection():
    """Test that the Verifier Agent rejects UPDATE queries."""
    question = "Update Max Verstappen's points to 1000."
    result = run_sql_query(question)
    
    assert "Query rejected" in result

