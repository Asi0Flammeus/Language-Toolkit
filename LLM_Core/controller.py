import os
from LLM_Core.view import CoreViewCLI

class CoreController():
    def __init__(self):
        self.view = CoreViewCLI()

        self.folder_path = self.view.get_folder_path()
        self.input_subfolder_name = os.path.basename(self.folder_path)
        self.files_to_process_names = self.get_files_to_process_names()

        self.current_file_path = ""
        self.current_content = ""

    def get_files_to_process_names():
        files_to_process_names = [
                f for f in os.listdir(self.folder_path)
                if any(f.endswith(ext) for ext in self.supported_extensions)
            ]
        return files_to_process_names

    def process_folder(self):
        for file_name in self.files_to_process_names:
            self.current_file_path = self.join_path_folder_with(file_name)
            self.load_content()
            self.process_content()

    def join_path_folder_with(file_name):
        return os.path.join(self.folder_path, file_name)

    def load_content(self):
        with open(self.current_file_path, 'r', encoding="utf-8") as f:
            self.current_content = f.read()

    def process_content(self):
        pass

    def check_existence_of_file(self, file_path):
        return os.path.exists(file_path)

    def save_content_to_file(self, destination_path):
        self.create_destination_if_needed(destination_path)
        with open(destination_path, "w", encoding="utf-8") as f:
            f.write(self.current_content)

    def create_destination_if_needed(self, destination_path):
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)

