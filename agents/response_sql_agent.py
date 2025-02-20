from utils_genai import PROMPTS, llm, usecase_context
from langchain_core.prompts import ChatPromptTemplate

class ResponseSqlAgent:
    def __init__(self):
        self.agent_name = "response_agent"

    def run(self, user_question: str, sql_status: bool, sql_result: str, sql_query: str) -> str:
        prompt_summary = PROMPTS['nl_reponse']
        prompt = ChatPromptTemplate.from_template(prompt_summary)
        chain = prompt | llm
        if sql_status:
            result = chain.invoke({"user_question": user_question,
                                    "sql_result": sql_result,
                                    "sql_query": sql_query, 
                                    "usecase_context": usecase_context})
        else:
            result = chain.invoke({"user_question": user_question,
                                    "sql_result": "SQL Agent failed to execute query with debugging, let the user know.",
                                    "sql_query": "NO SQL QUERY", 
                                    "usecase_context": usecase_context})
        return result