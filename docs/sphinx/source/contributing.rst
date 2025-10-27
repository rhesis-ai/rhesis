Contributing
============

Thank you for your interest in contributing to the Rhesis SDK! This document provides guidelines and instructions for contributing to the project.

Setting Up Development Environment
---------------------------------

1. Fork the repository on GitHub
2. Clone your fork locally:

   .. code-block:: bash

      git clone https://github.com/your-username/rhesis-sdk.git
      cd rhesis-sdk

3. Create a virtual environment and install development dependencies:

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
      pip install -e ".[dev]"

Development Guidelines
---------------------

Code Style
~~~~~~~~~

We follow PEP 8 and use Black for code formatting. Run the following before submitting your changes:

.. code-block:: bash

   black .
   flake8 .
   isort .

Testing
~~~~~~~

All new features should include tests. We use pytest for testing:

.. code-block:: bash

   pytest

Make sure all tests pass before submitting a pull request.

Documentation
~~~~~~~~~~~~

Please update the documentation when you add or modify features:

1. Add docstrings to all functions, classes, and methods
2. Update the relevant .rst files in the docs/source directory
3. Build and check the documentation locally:

   .. code-block:: bash

      cd docs
      make html
      # Open build/html/index.html in your browser

Pull Request Process
-------------------

1. Create a new branch for your feature or bugfix:

   .. code-block:: bash

      git checkout -b feature/your-feature-name

2. Make your changes and commit them with clear, descriptive commit messages

3. Push your branch to your fork:

   .. code-block:: bash

      git push origin feature/your-feature-name

4. Open a pull request on the original repository

5. Ensure the PR description clearly describes the problem and solution

6. Address any feedback from the maintainers

Code of Conduct
--------------

Please be respectful and inclusive when contributing to this project. We follow a code of conduct that promotes a positive and welcoming community for all contributors.

License
------

By contributing to the Rhesis SDK, you agree that your contributions will be licensed under the project's license.
