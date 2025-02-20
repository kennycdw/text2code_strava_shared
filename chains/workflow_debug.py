"""
For debugging of workflows, getting graphs and getting state snapshots.


How is the data stored in the state as we asked more questions?
Each thread has its own state, so the state is not shared between threads.
As the thread traverses through the nodes, the state is updated (returned) and the next node is invoked.
The messages are stored in the state as a list of messages (ensuring conversation history is maintained)
while the other fields are updated as the thread traverses through the nodes.
"""

import asyncio
from langchain_core.messages import HumanMessage
from chains.workflow_text2sql import app

thread = {"configurable": {"thread_id": "debug_2"}}


query = "What is the weather in sf?"
query = "Am I a morning or evening running person?"
query = "How many kilometers did the runner run last year?"
query = "How much did I run last year?"
query = "How many kudos do i get?"
query = "What is my longest run? Can you provide full metadata"
query = "What is my longest running streak?"
query = "Plot me a monthly running distance chart for 2024"
query = "What's my favorite day to run?"


hashed_strava_id = "4ik41YnN0F"

# when running the workflow, you can either do app.invoke, app.stream or app.batch
## for testing purposes, can call invoke:continue invoking and messages get fed into the list of messages
final_state = asyncio.run(app.ainvoke({"messages": [HumanMessage(content=query)], "hashed_strava_id": hashed_strava_id}, config=thread))

final_state.get("response_agent_result", "")

# Retrieve the state snapshot
state_snapshot = app.get_state({"configurable": {"thread_id": "debug_1"}})
state_snapshot.values.get("response_agent_result", "")

for message in final_state["messages"]:
    print(f"Message: {message}")

graph = app.get_graph()
# Save as PNG
with open("workflow_graph.png", "wb") as f:
    f.write(graph.draw_mermaid_png())
