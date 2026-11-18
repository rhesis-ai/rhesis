import sys

if sys.version_info < (3, 10):
    sys.exit("./rh project-migrate needs Python 3.10 or newer")

from project_migrate.cli import main

if __name__ == "__main__":
    main()
