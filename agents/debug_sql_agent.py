"""
Execute SQL Agent including debug and validate query
"""


from utils_genai import PROMPTS, llm
from langchain_core.prompts import ChatPromptTemplate

class DebugSqlAgent:
    def __init__(self):
        self.agent_name = "debug_sql_agent"

    def validate_sql(self, sql: str) -> str:
        # LLM sometimes returns ```sql and ``` so we need to remove them
        sql = sql.replace("```sql", "").replace("```", "").strip()
        return sql
    
    def debug_sql(self, user_question: str, sql: str, error_msg: str) -> str:
        prompt_summary = PROMPTS['debugsql_cloudsql-pg']
        prompt = ChatPromptTemplate.from_template(prompt_summary)
        chain = prompt | llm
        result = chain.invoke({"sql": sql,
                             "user_question": user_question,
                             "error_msg": error_msg})
        result.content = self.validate_sql(result.content)
        return result