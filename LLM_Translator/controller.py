from LLM_Core.controller import CoreController
from model import OpenaiTranslationModel
import time

class TranslatorController(CoreController):
    def __init__(self):
        super().__init__()

        self.supported_languages_codes = {
            "English": "en",
            "German": "de",
            "Spanish": "es",
            "Italian": "it",
            "Portuguese": "pt",
            "French": "fr"
        }
        self.supported_languages = list(self.supported_languages_codes.keys())
        self.code_languages = list(self.supported_languages_codes.values())
        self.translation_languages = self.view.get_languages()

        self.translated_text = ""
        self.translated_text_path = ""

        self.NUM_TRANSLATIONS = len(self.files_to_process_names) * len(self.translation_languages)
        self.start_time = time.time()
        self.processing_times = []
        self.index = 0

        self.model = None  # A model is instantiated for each translated text

    def translate_the_folder(self):
        for text_to_translate_name in self.files_to_process_names:
            self.current_file_path = os.path.join(self.folder_path, text_to_translate_name)
            self.load_content()
            self.load_translation_model()
            self.batch_translate_the_text()

    def load_translation_model(self):
        self.model = OpenaiTranslationModel(self.current_content)

    def batch_translate_the_text(self):
        for language in self.translation_languages:
            self.view.update_progress_bar(self.index, self.NUM_TRANSLATIONS)
            self.view.work_in_progress(f'Translating in {language}')

            self.create_translated_text_path_for(language)
            if not self.check_existence_of_file(self.translated_text_path):
                self.translated_text = self.model.get_translated_text_in(language)
                self.save_content_to_file(self.translated_text, self.translated_text_path)

            self.view.work_done(f'Translating in {language}')
            self.update_processing_times()
            self.estimate_remaining_time()

    def create_translated_text_path_for(self, language):
        extension = self.get_file_extension()
        self.translated_text_path = f"./outputs/{self.input_subfolder_name}/{os.path.splitext(os.path.basename(self.current_file_path))[0]}_{language}.{extension}"

    def update_processing_times(self):
        end_time = time.time()
        self.processing_times.append(end_time - self.start_time)

    def estimate_remaining_time(self):
        if self.index > 0:
            average_time = sum(self.processing_times) / len(self.processing_times)
            remaining_translations = self.NUM_TRANSLATIONS - (self.index + 1)
            SECONDS = average_time * remaining_translations
            self.view.estimated_remaining_time(SECONDS)
        self.index += 1

