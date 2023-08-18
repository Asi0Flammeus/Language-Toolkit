import os
from LLM_Core.view import CoreViewCLI

class TranslatorViewCLI(CoreViewCLI):
    def __init__(self, supported_languages):
        super().__init__()
        self.supported_languages = supported_languages

    def get_languages(self):
        """
        Allows the user to select from supported languages.
        """
        return self.get_selection_from_list("Select languages for translation:", self.supported_languages)

    def get_folder_to_translate_path(self):
        """
        Specialized folder selection method for translator input folder.
        """
        root_dir = "./inputs/"
        return self.get_folder_path(root_dir)

    def show_translated_content(self, content_type, translated_content):
        """
        Display translated content to the user.

        content_type: str - e.g., "transcript", "lecture", etc.
        translated_content: str - the translated content to display.
        """
        self.display_message(f"Translated {content_type}: {translated_content}")

    def estimated_remaining_time(self, seconds_remaining):
        """
        Display estimated time remaining.
        """
        m, s = divmod(seconds_remaining, 60)
        h, m = divmod(m, 60)
        self.display_message(f'Estimated time remaining: {int(h)} hours, {int(m)} minutes, and {int(s)} seconds')

    def user_request_stop(self):
        """
        Prompt the user to ask if they want another batch translation.
        """
        return not self.ask_yes_no("Do you want another batch translation?")

