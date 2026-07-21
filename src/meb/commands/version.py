from info import APP_NAME, APP_VERSION, APP_AUTHOR, APP_GITHUB, APP_WEBSITE


def run():
    print(f"{APP_NAME}, {APP_VERSION}")
    print(f"Créateur : {APP_AUTHOR}")
    print(f"GitHub   : {APP_GITHUB}")
    print(f"Site web : {APP_WEBSITE}")

if __name__ == "__main__":
    run()
