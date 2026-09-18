# My 10x Solution

## 1. What is the problem you are solving?
F1 Fantasy players struggle to make mathematically sound transfer decisions due to inherent fan bias and the cognitive load of balancing complex rules. Specifically, they must manage a strict $100M budget, anticipate driver price changes over multiple weeks, and evaluate if taking a -4 point penalty for extra transfers is mathematically worth it. This project solves that by providing an objective, conversational AI analyst. 

**Who has this problem:** Casual and competitive F1 Fantasy players who want to optimize their teams.
**10x Claim:** Evaluating multi-week transfer scenarios and identifying undervalued drivers becomes 10x faster and entirely objective, removing emotional bias from complex budget decisions.
**Non-goal:** We will NOT build an autonomous bot that submits actual transfers to the official F1 Fantasy game.

## 2. How did you implement your solution?
This solution is a backend decision-support system built with Python, FastAPI, DuckDB, and LangChain. 

**The 5 Concepts Implemented:**
1. **API Endpoints:** FastAPI backend handling chat and team management.
2. **Database:** DuckDB persisting user accounts, their Fantasy team state, and seeded F1 data.
3. **Authentication:** JWT-based login so users can manage their specific team securely.
4. **LLM Integration:** LangChain + Gemini AI reasoning layer to explain decisions and analyze scenarios.
5. **Agent with guardrails (Swap):** Replaces background jobs/caching. The AI acts strictly inside F1 analysis limits, utilizing LangChain tools to enforce deterministic logic and reject generic chat.

**Steps to run:**
*(To be finalized in M4)*
