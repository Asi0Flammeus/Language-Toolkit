import os

class CoreViewCLI():
    def __init__(self):
        pass  # No initialization required for now, but can be expanded in the future.

    def get_selection_from_list(self, prompt, items_list):
        """
        Allows a user to select from a given list of items.
        """
        print()
        print(prompt)
        for i, item in enumerate(items_list):
            print(f"{i+1}. {item}")

        while True:
            choice_input = input(f"Enter the number of your choice (1-{len(items_list)}): ")
            if self.validate_choice(choice_input, len(items_list)):
                choice = int(choice_input)
                break

        return items_list[choice-1]

    def validate_choice(self, choice_input, length):
        try:
            choice = int(choice_input)
            if 1 <= choice <= length:
                return True
            else:
                print("Invalid choice. Please enter a number within the range. \n")
                return False
        except ValueError:
            print("Invalid input format. \n")
            return False

    def get_folder_path(self, root_dir):
        """
        Allows a user to select a folder from the root directory.
        """
        folders = [f.path for f in os.scandir(root_dir) if f.is_dir()]
        return self.get_selection_from_list("Select a folder:", folders)

    def update_progress(self, current, total):
        progress = current / total * 100
        print(f'Progress: [{current}/{total}] {progress:.2f}%')

    def display_message(self, message):
        """
        Display a general message to the user.
        """
        print()
        print(message)

    def ask_yes_no(self, question):
        """
        Prompt a user with a yes or no question.
        """
        while True:
            response = input(question + " (y/n): ").lower()
            if response in ["y", "n"]:
                return response == "y"
            else:
                print("Invalid input. Please enter y or n. \n")

