from utils_genai import PROMPTS, llm
from langchain_core.prompts import ChatPromptTemplate
from langchain.output_parsers import StructuredOutputParser, ResponseSchema


class VisualizationAgent:
    def __init__(self):
        self.agent_name = "visualization_agent"
        self.visualization_type_list = [
            "",
            "table",
            "bullet",
            "bar",
            "column",
            "line",
            "area",
            "pie",
            "scatter",
            "bubble",
            "histogram",
            "map",
            "gantt",
            "heatmap",
        ]

    def generate_visualization_type(self, user_question: str, sql_query: str) -> str:
        """
        Generate the most suitable chart type for the given question and data.

        Format:
        {
            "chart_type": "bar"
        }

        parser.get_format_instructions()
        ```json
        {
                "chart_type": string  // One of the allowed chart types from the list.
        }
        ```
        """
        response_schemas = [
            ResponseSchema(
                name="chart_type", description="One of the allowed chart types from the list.", type="string", enum=self.visualization_type_list
            )
        ]
        parser = StructuredOutputParser(response_schemas=response_schemas)

        prompt_summary = PROMPTS["visualization_type_prompt"]
        prompt = ChatPromptTemplate.from_template(prompt_summary)
        chain = prompt | llm | parser
        result = chain.invoke({"user_question": user_question, "sql_query": sql_query, "format_instructions": parser.get_format_instructions()})
        return result

    def route_question(self, chart_type: str) -> str:
        # TODO
        if chart_type == "":
            return "END"
        else:
            return "VISUALIZATION_CODE_AGENT"

    def generate_visualization_code(self, user_question: str, sql_query: str, sql_results: str, chart_type: str) -> str:
        prompt_summary = PROMPTS["visualization_code_prompt"]
        prompt = ChatPromptTemplate.from_template(prompt_summary)
        chain = prompt | llm
        result = chain.invoke({"sql_query": sql_query, "sql_results": sql_results, "user_question": user_question, "chart_type": chart_type})
        return result

    def html_parser(self, html_string: str) -> str:
        html_content = html_string.strip("`").lstrip("html\n")
        html_content = html_content.rstrip("```\n")
        return html_content


"""
debug purposes

from chains.workflow_text2sql import app
import asyncio
from langchain_core.messages import HumanMessage

thread = {"configurable": {"thread_id": "debug_2"}}
hashed_strava_id = "4ik41YnN0F"
query = "What is my longest distance run?"
query = "Plot me a monthly running distance chart"
final_state = asyncio.run(app.ainvoke({"messages": [HumanMessage(content=query)], "hashed_strava_id" : hashed_strava_id}, config = thread))
user_question = final_state['user_question']
sql_query = final_state['sql_query']
sql_results = final_state['execute_sql_result']

visualization_agent = VisualizationAgent()

visualization_agent.visualization_type_list
visualization_type_response = visualization_agent.generate_visualization_type(user_question, sql_query)
chart_type = visualization_type_response['chart_type']

# need a routing option - for empty string.

code = visualization_agent.generate_visualization_code(user_question, sql_query, sql_results, chart_type)
print(code.content)

html_content = code.content.strip('`').lstrip('html\n')
with open('visualization.html', 'w') as f:
    f.write(html_content)
"""
