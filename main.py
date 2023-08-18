from LLM_Core.controller import CoreController
from LLM_Core.view import CoreViewCLI

def main():
    view = CoreViewCLI()

    while True:
        controller = CoreController()
        controller.process_folder()

        if view.user_request_stop():
            break

if __name__ == "__main__":
    main()

