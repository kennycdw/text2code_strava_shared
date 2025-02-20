from utils_genai import PROMPTS, llm, embeddings
from langchain_core.prompts import ChatPromptTemplate
from app_instance import db, sg_timezone
from datetime import datetime, timezone
import asyncio
from loguru import logger


class RetrievalAgent:
    def __init__(self):
        self.agent_name = "retrieval_agent"

    def embed_kgq(self, user_question: str) -> str:
        vector = embeddings.embed_query(user_question)
        return vector

    def format_kgq_list(self, kgq_list: list) -> str:
        """
        Format the list of known good queries into a prompt.

        Example:
        kgq_list = [{'user_question': 'What is my latest run?', 'query': '', 'cosine_similarity': 0.636946109833138}]
        """
        formatted_kgq_str = ""
        for kgq in kgq_list:
            formatted_kgq_str += f"User question: {kgq['user_question']}\nQuery: {kgq['query']}\nCosine similarity: {kgq['cosine_similarity']}\n\n"
        return formatted_kgq_str

    async def store_kgq_in_db(self, user_question: str) -> str:
        """Store a known good query and its embedding in the database
        
        Args:
            prompt (str): The query text to store
            query_type (str, optional): The type of query (e.g., 'run', 'ride', etc.)
        """
        vector = self.embed_kgq(user_question)
        # Convert the list to a Postgres vector string format
        vector_str = f"[{','.join(map(str, vector))}]"

        # Create data dictionary for upsert
        data = {
            'user_question': user_question,
            'user_question_embedding': vector_str,
            'query_type': 'sql',
            'updated_at': datetime.now(timezone.utc).astimezone(sg_timezone)
        }
        
        # Use the database upsert method
        await db.upsert(
            table='main.known_good_queries',
            data=data,
            constraint_columns=["user_question"]
        )

    async def retrieve_kgq_from_db(self, user_question: str) -> str:
        # Embed the user question
        vector = self.embed_kgq(user_question)
        # SQL query using cosine similarity to find top 3 matches
        query = """
            SELECT 
                user_question,
                query,
                1 - (user_question_embedding <=> $1::vector) as cosine_similarity
            FROM main.known_good_queries 
            WHERE query IS NOT NULL
            ORDER BY cosine_similarity DESC
            LIMIT 3
        """
        results = await db.fetch_all(query, [vector])
        formatted_kgq_str = self.format_kgq_list(results)
        return formatted_kgq_str

"""
For debugging purposes

asyncio.run(db.connect())
retrieval_agent = RetrievalAgent()
user_question = "What is my latest ride?"
asyncio.run(retrieval_agent.store_kgq_in_db(user_question))

asyncio.run(retrieval_agent.retrieve_kgq_from_db(user_question))
"""