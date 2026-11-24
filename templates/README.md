# Agent Template (Student Guide)

Use this template when you need to **define a new agent** for a LangGraph lab.

Reference implementation in the labs: `labs/Day2_Advanced/agents/`  
(`PlannerAgent`, `ResearcherAgent`, `CoderAgent`, `ReviewerAgent`)

## Files

| File | Purpose |
|------|---------|
| [`agent_template.py`](agent_template.py) | Copy/rename this to create a new agent |
| This README | Checklist + wiring steps |

## Agent checklist

Every agent should have:

1. **Clear single responsibility** — one job (plan / research / code / review / …)
2. **System prompt in constants** — do not hardcode long prompts inside methods
3. **Structured output (Pydantic)** — when the result must be machine-usable
4. **Public method** — e.g. `run(...)` / `create_plan(...)` that returns a plain `dict`
5. **Retries** — wrap LLM calls with a retry helper for transient failures
6. **Fallback** — return a safe default if the LLM fails
7. **Timestamp / task_id** — so graph nodes can audit and merge state
8. **No secrets** — never put API keys inside the agent file

## How to create a new agent

1. Copy the template:
   ```bash
   cp templates/agent_template.py labs/Day2_Advanced/agents/my_agent.py
   ```
2. Rename the class, schema, and method to match the agent’s job.
3. Add prompts / temperature to `utils/constants.py`.
4. Implement the LLM call + return shape.
5. Export it from `agents/__init__.py`.
6. Wire it into the graph:
   - `workflow.add_node("my_agent", self.my_agent_node)`
   - call `self.my_agent.run(task, context)` inside the node

## Minimal wiring example

```python
# agents/my_agent.py
from agents.my_agent import MyAgent

# graph/multi_agent_graph.py
self.my_agent = MyAgent()

def my_agent_node(self, state):
    task = ...  # pick from state["tasks"]
    result = self.my_agent.run(task, context=self._build_context(state))
    return {
        "tasks": [{**task, "status": result["status"], "result": result.get("output")}],
        "agent_history": [{"agent": "my_agent", "action": "ran", "task_id": task["id"]}],
    }
```

## Recommended return shape

```python
{
    "task_id": "...",
    "output": "...",          # main work product
    "status": "completed",    # or "failed"
    "timestamp": "...",
    # optional extras: sources, score, artifacts, ...
}
```

The **graph node** owns routing and state reducers. The **agent class** owns LLM logic only.
