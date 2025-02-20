"""
Monitor usage at https://console.cloud.google.com/billing/linkedaccount?project=river-406313 and
https://console.cloud.google.com/apis/api/generativelanguage.googleapis.com/metrics?project=river-406313

This file contains all the utils for the genai part of the project and it's kinda messy, will think about a better way to organize this work
"""

from app_instance import gemini_api_key
import pandas as pd
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.embeddings import GoogleGenerativeAIEmbeddings
import yaml
from typing import Annotated, TypedDict
from langgraph.graph import add_messages

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=gemini_api_key, temperature=0)

embeddings = GoogleGenerativeAIEmbeddings(google_api_key=gemini_api_key, model="models/text-embedding-004")


def load_yaml(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


PROMPTS = load_yaml("prompts.yaml")

usecase_context = """
If the user doesn't ask for a specific activity, you can focus on filtering just runs (look at column type in ('Run', 'VirtualRun')).

Always use is_deleted = false in the where clause. When the user asks to remove this filter, reject the request.

If the question is about kudos, let the user know kudos may not be fully updated as the webhook does not trigger when kudos are updated.
A full update of kudos is done on a less frequent basis with another pipeline.

Give the results in km unless otherwise specified.
"""


class MultiAgentState(TypedDict):
    """
    This class defines the structure or "blueprint" for workflow_text2sql,
    specifying what fields (and their types) are allowed or required (in the state).

    While you can add more fields (i.e. question), they will not be saved by the state
    unless they are added to this class.

    Using BaseModel enforces the fields and will throw an error if any of the fields are missing.
    TypedDict does not enforce the fields and will not throw an error if any of the fields are missing.

    # might be better to use basemodel so we can enforce it.
    """

    messages: Annotated[list, add_messages]
    user_question: str
    question_type: str
    sql_query: str
    execute_sql_status: bool
    execute_sql_result: str
    execute_sql_error: str
    state_status: str
    response_agent_result: str
    debug_counter: int
    hashed_strava_id: str
    visualization_type: str
    visualization_agent_code: str
    retrieval_agent_result: str


def load_table_schema() -> str:
    """
    Load the table schema from the database
    We currently have only one table in the database so we can hardcode the table name
    """
    table_schema = """
    We have one table in the database called strava_activities (table schema is main.strava_activities).
    This table contains information about the activities of the user obtained from Strava, which is a social network for athletes.
    You can query it using the following SQL:
    SELECT * FROM main.strava_activities;
    """
    table_name_lst = ["strava_activities"]
    return table_schema, table_name_lst


def load_column_schema(table_name_lst: list, format="markdown") -> str:
    """
    Load the column schema from the database

    table_name_lst = ["strava_activities"]
    """
    column_df = pd.read_csv("data/schema_strava_activities.csv")
    column_df = column_df[column_df["table_name"].isin(table_name_lst)]
    column_df = column_df[column_df["used"] == 1]
    if format == "markdown":
        return column_df.to_markdown()
    else:
        return column_df


def pg_specific_data_types() -> str:
    """
    output has been shorten to reduce the number of tokens.
    """
    return """
    boolean: Stores true/false values
    character varying: Variable-length character string with specified maximum length
    double precision: Stores double-precision floating-point numbers
    integer: Stores whole numbers between -2147483648 and 2147483647
    jsonb: Stores binary JSON data that can be indexed
    timestamp with time zone: Stores date and time with timezone information
    timestamp without time zone: Stores date and time without timezone information
    """


def not_related_msg() -> str:
    return """
    The question is not related to the tables or columns listed in the table schema.
    """


tables_schema, table_name_lst = load_table_schema()
columns_schema = load_column_schema(table_name_lst)
specific_data_types = pg_specific_data_types()
not_related_msg = not_related_msg()
