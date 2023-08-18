import os
import pytest
from LLM_Core.controller import CoreController
import tempfile

class TestCoreController:

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.temporary_directory = tempfile.mkdtemp()
        self.created_files = []

        yield

        for f in self.created_files:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(self.temporary_directory):
            os.rmdir(self.temporary_directory)

    @pytest.fixture(autouse=True)
    def init_controller(self):
        self.controller = CoreController()

    def test_create_destination_if_needed(self):
        non_existent_path = os.path.join(self.temporary_directory, "non_existent_folder", "test.txt")
        self.controller.create_destination_if_needed(non_existent_path)
        assert os.path.exists(os.path.dirname(non_existent_path)), "Director should have been created"

        existent_folder = os.path.join(self.temporary_directory, "existent_folder")
        os.makedirs(existent_folder)
        existent_file = os.path.join(existent_folder, "test.txt")
        self.controller.create_destination_if_needed(existent_file)
        assert os.path.exists(existent_folder), "Existing directory should still be present"
        assert not os.path.exists(existent_file), "File should not be created"

    def test_load_content(self):
        test_file = os.path.join(self.temporary_directory, "test.txt")
        self.created_files.append(test_file)
        with open(test_file, 'w') as f:
            f.write("Hello, LLM!")
        self.controller.current_file_path = test_file
        self.controller.load_content()
        assert self.controller.current_content == "Hello, LLM!"

    def test_save_content_to_file(self):
        test_output = os.path.join(self.temporary_directory, "output.txt")
        self.created_files.append(test_output)
        test_content = "Save this content."
        self.controller.save_content_to_file(test_content, test_output)
        with open(test_output, 'r') as f:
            content = f.read()
            assert content == test_content

    def test_get_file_extension(self):
        self.controller.current_file_path = "example.md"
        assert self.controller.get_file_extension() == "md"
        self.controller.current_file_path = "test.file.txt"
        assert self.controller.get_file_extension() == "txt"

    def test_check_existence_of_file(self):
        test_file = os.path.join(self.temporary_directory, "existent.txt")
        self.created_files.append(test_file)
        with open(test_file, 'w') as f:
            f.write("I exist.")
        assert self.controller.check_existence_of_file(test_file)
        assert not self.controller.check_existence_of_file("non_existent.txt")

