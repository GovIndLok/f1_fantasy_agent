import duckdb
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI


def run_f1_agent(prompt: str, player_id: str, db: duckdb.DuckDBPyConnection) -> dict:
    @tool
    def get_my_team() -> str:
        """Returns the current roster for the user."""
        res = db.execute("SELECT r.entity_type, d.name, d.current_price FROM rosters r JOIN drivers d ON r.entity_id = d.driver_id WHERE r.player_id = ? AND r.entity_type = 'driver'", [player_id]).fetchall()
        c_res = db.execute("SELECT r.entity_type, c.name, c.current_price FROM rosters r JOIN constructors c ON r.entity_id = c.constructor_id WHERE r.player_id = ? AND r.entity_type = 'constructor'", [player_id]).fetchall()
        budget = db.execute("SELECT budget FROM players WHERE player_id = ?", [player_id]).fetchone()
        if not budget:
            db.execute("INSERT INTO players VALUES (?, 'new_manager', 100.00)", [player_id])
            budget = (100.00,)
            
        team_str = f"Budget Remaining: ${budget[0]}M\n"
        team_str += "Drivers:\n" + "\n".join([f"- {r[1]} (${r[2]}M)" for r in res])
        team_str += "\nConstructors:\n" + "\n".join([f"- {r[1]} (${r[2]}M)" for r in c_res])
        return team_str
        
    @tool
    def get_driver_price(name: str) -> str:
        """Gets the price of a driver by name (e.g., 'Max Verstappen')."""
        res = db.execute("SELECT name, current_price FROM drivers WHERE name ILIKE ?", [f"%{name}%"]).fetchone()
        if res:
            return f"{res[0]} costs ${res[1]}M"
        return f"Driver {name} not found."

    tools = [get_my_team, get_driver_price]
    
    # Initialize the LLM (will raise ValidationError if API key not found)
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    system_message = "You are a strict F1 Fantasy Analyst. You ONLY discuss Formula 1 and Fantasy transfers. If a user asks about anything else, politely refuse to answer. You have access to tools to check the user's team and driver prices."
    
    agent = create_agent(llm, tools, system_prompt=system_message)
    
    try:
        response = agent.invoke({"messages": [("user", prompt)]})
        content = response["messages"][-1].content
        final_message = content if isinstance(content, str) else str(content)
        estimated_tokens = len(prompt.split()) + len(final_message.split())
        return {"answer": final_message, "cost_log": {"total_tokens": estimated_tokens}}
    except Exception as e:
        return {"answer": f"Error: {str(e)}", "cost_log": {"total_tokens": 0}}
