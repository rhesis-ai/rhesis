Installation
============

This page provides detailed installation instructions for the Rhesis SDK.

Requirements
-----------

* Python 3.8 or higher
* pip (Python package installer)

Installing with pip
------------------

The recommended way to install the Rhesis SDK is using pip:

.. code-block:: bash

   pip install rhesis-sdk

This will install the latest stable version of the SDK.

Installing from Source
---------------------

If you want to install the development version, you can install directly from the GitHub repository:

.. code-block:: bash

   pip install git+https://github.com/rhesis/rhesis-sdk.git

Verifying Installation
---------------------

To verify that the Rhesis SDK has been installed correctly, run:

.. code-block:: python

   import rhesis

   print(rhesis.__version__)

This should print the version number of the installed SDK.
