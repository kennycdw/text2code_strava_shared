from utils_genai import (PROMPTS, llm,
                         usecase_context, tables_schema, columns_schema, specific_data_types, not_related_msg)
from langchain_core.prompts import ChatPromptTemplate



class BuildSqlAgent:
    def __init__(self):
        self.agent_name = "build_sql_agent"

    def rewrite_prompt(self, prompt: str) -> str:
        """
        TODO: not implemented yet
        """

        # TODO: get the formatted history from the session history
        formatted_history = """
        """
        prompt_rewrite = PROMPTS['rewrite_prompt']

        prompt = ChatPromptTemplate.from_template(prompt_rewrite)

        chain = prompt | llm

        return chain.invoke({"user_question": prompt,
                      "formatted_history": formatted_history,
                      })

    def validate_sql(self, sql: str) -> str:
        # TODO: add more validation like hashed_strava_id and is_deleted = false


        # LLM sometimes returns ```sql and ``` so we need to remove them
        sql = sql.replace("```sql", "").replace("```", "").strip()
        return sql
    

    def run(self, user_question: str, hashed_strava_id: str, similar_sql: str) -> str:
        prompt_text2sql = PROMPTS['buildsql_cloudsql-pg']

        prompt = ChatPromptTemplate.from_template(prompt_text2sql)

        chain = prompt | llm

        user_strava_id_prompt= f", Use hashed_strava_id = {hashed_strava_id} in the where clause."
        modified_user_question = user_question + user_strava_id_prompt

        result = chain.invoke({"user_question": modified_user_question,
                      "tables_schema": tables_schema,
                      "columns_schema": columns_schema, 
                      "usecase_context": usecase_context,
                      "similar_sql": similar_sql,
                      "specific_data_types": specific_data_types, 
                      "not_related_msg": not_related_msg,
                      })
        result.content = self.validate_sql(result.content)
        return result



"""
For debugging purposes

prompt = "What is the average distance of all activities?"
agent = BuildSqlAgent()
agent.run(prompt)
"""


