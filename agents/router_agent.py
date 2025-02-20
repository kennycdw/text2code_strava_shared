from utils_genai import PROMPTS, llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from utils_genai import MultiAgentState


# this is memory less, memory is retained at the langraph workflow level
class RouterAgent:
    def __init__(self):
        self.agent_name = "router_agent"
        self.question_category_prompt = PROMPTS['router_prompt']
        
    def route_question(self, state: MultiAgentState) -> str:
        """
        state = {'messages': [HumanMessage(content='what is the weather in sf', additional_kwargs={}, response_metadata={}, id='9ec55628-cd93-42f2-9757-252fe305bcb9'), AIMessage(content='GENERAL', additional_kwargs={}, response_metadata={}, id='df4933df-874f-44ba-9369-4e83910f8988')], 'question_type': 'GENERAL'}
        """
        return state['question_type']

    def validate_question_type(self, question_type: str) -> bool:
        # the LLM keeps returning a new line break for some reason so some custom cleansing is needed
        question_type = question_type.strip()
        if question_type not in ['DATABASE', 'GENERAL']:
            raise ValueError(f"Invalid question type: {question_type}")
        return question_type

    def run(self, prompt: str) -> str:
        """
        sample of result:
        content='GENERAL\n' additional_kwargs={} response_metadata={'prompt_feedback': {'block_reason': 0, 'safety_ratings': []}, 'finish_reason': 'STOP',
        'safety_ratings': [{'category': 'HARM_CATEGORY_HATE_SPEECH', 'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT',
          'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_HARASSMENT', 'probability': 'NEGLIGIBLE', 'blocked': False},
          {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'probability': 'NEGLIGIBLE', 'blocked': False}]} id='run-e79e8d8f-db5c-432b-936f-9a9637ffb7ca-0' 
          usage_metadata={'input_tokens': 103, 'output_tokens': 2, 'total_tokens': 105, 'input_token_details': {'cache_read': 0}}
        """
        question_category_prompt = ChatPromptTemplate.from_template(self.question_category_prompt)
        question_category_chain = question_category_prompt | llm
        result = question_category_chain.invoke({"question": prompt}) #last_message.content
        result.content = self.validate_question_type(result.content) # cleans and updates the content
        return result