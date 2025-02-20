"""
Workflow for text2sql
"""

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from agents.router_agent import RouterAgent
from agents.response_general_agent import ResponseGeneralAgent
from agents.retrieval_agent import RetrievalAgent
from agents.build_sql_agent import BuildSqlAgent
from agents.response_sql_agent import ResponseSqlAgent
from agents.debug_sql_agent import DebugSqlAgent
from agents.visualization_agent import VisualizationAgent
from utils_genai import MultiAgentState
from app_instance import db
import asyncio


def router_node(state: MultiAgentState) -> MultiAgentState:
    """
    Example of state input from first node: print(state)
     {'messages': [HumanMessage(content='what is the weather in sf', additional_kwargs={}, response_metadata={}, id='ece2797f-302b-4baa-8f00-58fb2f70b2ed')]}
    """
    # Get the last message's content as our question
    last_message = state["messages"][-1]
    result = router_agent.run(last_message.content)
    # Don't need to return all fields, just update all the fields this node is responsible for
    return {
        "question_type": result.content,
        "user_question": last_message.content,
        "state_status": "TBC",
        "debug_counter": 0,
        "execute_sql_status": False,
        "execute_sql_result": "",
        "execute_sql_error": "",
        "response_agent_result": "",
        "sql_query": "",
        "retrieval_agent_result": "",
    }


def response_general_node(state: MultiAgentState) -> MultiAgentState:
    result = response_general_agent.run(state["user_question"])
    return {
        "messages": [AIMessage(content=result.content)],
        "question_type": "GENERAL",
        "state_status": "TBC",
        "response_agent_result": result.content,
        "visualization_type": "",
        "visualization_agent_code": "",
    }


async def retrieval_node(state: MultiAgentState) -> MultiAgentState:
    formatted_kgq_str = await retrieval_agent.retrieve_kgq_from_db(state["user_question"])
    return {"state_status": "TBC", "retrieval_agent_result": formatted_kgq_str}


def build_sql_node(state: MultiAgentState) -> MultiAgentState:
    result = build_sql_agent.run(
        state["user_question"], state["hashed_strava_id"], state["retrieval_agent_result"]
    )  # feed in the last message's content
    return {"sql_query": result.content, "state_status": "TBC"}


def response_sql_node(state: MultiAgentState) -> MultiAgentState:
    if state["execute_sql_status"]:
        result = response_sql_agent.run(state["user_question"], state["execute_sql_status"], state["execute_sql_result"], state["sql_query"])
        return {"messages": [AIMessage(content=result.content)], "state_status": "TBC", "response_agent_result": result.content}
    else:
        return {"messages": [AIMessage(content="Error executing SQL query")], "state_status": "TBC"}


def debug_sql_node(state: MultiAgentState) -> MultiAgentState:
    result = debug_sql_agent.debug_sql(user_question=state["user_question"], sql=state["sql_query"], error_msg=state["execute_sql_error"])
    return {"sql_query": result.content, "state_status": "TBC", "debug_counter": state["debug_counter"] + 1}


def router_execute_debug_node(state: MultiAgentState) -> MultiAgentState:
    if state["execute_sql_status"] or state["debug_counter"]:
        return "RESPONSE"
    else:
        return "DEBUG"


def visualization_node(state: MultiAgentState) -> MultiAgentState:
    visualization_type_response = visualization_agent.generate_visualization_type(state["user_question"], state["sql_query"])
    chart_type = visualization_type_response["chart_type"]
    if chart_type != "":
        result = visualization_agent.generate_visualization_code(state["user_question"], state["sql_query"], state["execute_sql_result"], chart_type)
        code = result.content
        code = visualization_agent.html_parser(code)
    else:
        code = ""
    return {"state_status": "TBC", "visualization_agent_code": code, "visualization_type": chart_type}


router_agent = RouterAgent()
response_general_agent = ResponseGeneralAgent()
retrieval_agent = RetrievalAgent()
build_sql_agent = BuildSqlAgent()
response_sql_agent = ResponseSqlAgent()
debug_sql_agent = DebugSqlAgent()
visualization_agent = VisualizationAgent()
asyncio.run(db.connect())

workflow_tester = StateGraph(MultiAgentState)
workflow_tester.add_node("router", router_node)  # first parameter is the name, second is the function that will be called (with a state as input)
workflow_tester.add_node("response_general", response_general_node)
workflow_tester.add_node("retrieval", retrieval_node)
workflow_tester.add_node("build_sql", build_sql_node)
workflow_tester.add_node("execute_sql", db.text2sql_execute)
workflow_tester.add_node("response_sql", response_sql_node)
workflow_tester.add_node("debug_sql", debug_sql_node)
workflow_tester.add_node("visualization", visualization_node)

workflow_tester.set_entry_point("router")  # set the entry point to the router node

# 1) upstream node, 2) function that will be called, 3) dictionary of conditions (key) and the node names (values) to route to
workflow_tester.add_conditional_edges("router", router_agent.route_question, {"DATABASE": "retrieval", "GENERAL": "response_general"})
workflow_tester.add_edge("response_general", END)  # the two parameters represents the name of the nodes (source and destination)
workflow_tester.add_edge("retrieval", "build_sql")
workflow_tester.add_edge("build_sql", "execute_sql")
workflow_tester.add_conditional_edges("execute_sql", router_execute_debug_node, {"DEBUG": "debug_sql", "RESPONSE": "response_sql"})
workflow_tester.add_edge("debug_sql", "execute_sql")
workflow_tester.add_edge("response_sql", "visualization")
workflow_tester.add_edge("visualization", END)

checkpointer = MemorySaver()
app = workflow_tester.compile(checkpointer=checkpointer)
