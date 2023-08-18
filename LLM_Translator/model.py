import os
from LLM_Core.model import BaseModel, APIErrorHandler, ContentChunk

class OpenaiTranslationModel(BaseModel):
    """
    This class provides the methods for using a LLM specifically for translation.
    """

    def __init__(self, text_to_translate):
        super().__init__(text_to_translate)
        self.model_engine = "gpt-3.5-turbo"
        self.error_handler = APIErrorHandler()
        self.temperature = 0.1

    def set_prompt_for(self, operation):
        """
        Overrides the base method to set the translation-specific prompt.
        """
        language = operation
        self.prompt = (f"translate the following text into {language}."
                       " Do not translate path links. "
                       "The output must have the same markdown layout as the original text:\n")

    def get_translated_text_in(self, language):
        return self.process_content(language)

