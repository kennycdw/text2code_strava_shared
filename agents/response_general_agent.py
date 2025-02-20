from utils_genai import (PROMPTS, llm,
                         usecase_context, tables_schema, columns_schema, specific_data_types, not_related_msg)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage

class ResponseGeneralAgent:
    def __init__(self):
        self.agent_name = "general_agent"
        #self.question_category_prompt = PROMPTS['question_category']
        # TODO: add more context on how you are built and add user flow
        self.general_prompt = """
            You're Kenny personal assistant. Your task is to provide insights on your data form Strava.

            If the user asks for a summary or a dashboard, direct them to the telegram bot (https://t.me/StravaKennyBot).
            
            Answer the questions based on the user response. Do not hallucinate and do not make up information especially on strava workout data.
            Question: {question}
            """

    def run(self, user_question: str) -> str:
        general_prompt = ChatPromptTemplate.from_template(self.general_prompt)
        general_prompt_chain = general_prompt | llm
        result = general_prompt_chain.invoke({"question": user_question})
        return result