import os
import time
import openai
import tiktoken
from dotenv import load_dotenv
from openai.error import RateLimitError, Timeout, APIError, ServiceUnavailableError

class BaseModel:
    """
    This class provides the methods for using a Language Model.
    """
    def __init__(self, content):
        self.content = ContentChunk(content)

        load_dotenv()
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.model_engine = "gpt-3.5-turbo"
        self.error_handler = APIErrorHandler()

        self.prompt = ""
        self.temperature = 0.1

    def process_content(self, operation):
        self.set_prompt_for(operation)
        processed_chunks = []
        NUM_CHUNKS = len(self.content.chunks)
        for i, chunk in enumerate(self.content.chunks):
            processed_chunk = self.process_single(chunk)
            processed_chunks.append(processed_chunk)
            print(f'Progress: {(((i+1)/NUM_CHUNKS)*100):.2f}% of chunks processed.')
        processed_text = "\n".join(processed_chunks)
        return processed_text

    def set_prompt_for(self, operation):
        raise NotImplementedError

    def process_single(self, chunk):
        try:
            current_prompt = self.prompt + chunk
            return self.get_response_from_OpenAI_API_with(current_prompt)
        except Exception as e:
            self.error_handler.handle_error(e)
            return self.process_single(chunk)

    def get_response_from_OpenAI_API_with(self, current_prompt):
        response = openai.ChatCompletion.create(
            model = self.model_engine,
            messages=[
                {"role": "user", "content": current_prompt}
            ],
            temperature=self.temperature
        )
        return response['choices'][0]['message']['content']


class ContentChunk:
    def __init__(self, content):
        self.content = content
        self.chunks = []
        self.current_chunk = ""
        self.encoding_name = "cl100k_base"
        self.MAX_TOKENS = 750

        self.create_chunks()

    def create_chunks(self):
        paragraphs = self.content.splitlines()
        for paragraph in paragraphs:
            if self.can_add_another(paragraph):
                self.current_chunk += paragraph + "\n"
            else:
                self.chunks.append(self.current_chunk.strip())
                self.current_chunk = paragraph
        if self.current_chunk:
           self.chunks.append(self.current_chunk.strip())

    def can_add_another(self, paragraph):
        CHUNK_TOKENS = self.count_the_token_length_of(self.current_chunk)
        PARAGRAPH_TOKENS = self.count_the_token_length_of(paragraph)
        return CHUNK_TOKENS + PARAGRAPH_TOKENS <= self.MAX_TOKENS

    def count_the_token_length_of(self, string):
        encoding = tiktoken.get_encoding(self.encoding_name)
        NUM_TOKENS = len(encoding.encode(string))
        return NUM_TOKENS


class APIErrorHandler:
    def __init__(self):
        self.error_handlers = {
            RateLimitError: "Rate limit",
            Timeout: "Timeout",
            APIError: "API",
            ServiceUnavailableError: "Service Unavailable",
        }
        self.sleep_time = 5

    def handle_error(self, error):
        error_type = type(error)
        error_message = self.error_handlers.get(error_type, f"{error}")
        print(f"An {error_message} error occured. Retry in {self.sleep_time} seconds...")
        time.sleep(self.sleep_time)

