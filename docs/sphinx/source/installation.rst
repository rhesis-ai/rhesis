Installation
============

This page provides detailed installation instructions for the Rhesis SDK.

Requirements
-----------

* Python 3.12 or higher
* pip (Python package installer)

Installing with pip
------------------

The recommended way to install the Rhesis SDK is using pip:

.. code-block:: bash

   pip install rhesis-sdk

This installs the core SDK, which connects your application to Rhesis: the connector,
``@endpoint``, ``@observe`` and tracing, ``RhesisClient`` and the entities, ``@metric``, and the
native judges and synthesizers with the Rhesis-hosted model.

For other model providers, DeepEval and DeepTeam metrics, document extraction and chunking, and
MCP agents, install every SDK feature:

.. code-block:: bash

   pip install "rhesis-sdk[all]"

Local Hugging Face models need the ``huggingface`` extra, for example
``pip install "rhesis-sdk[all,huggingface]"``. See
`What to install <https://docs.rhesis.ai/sdk/installation#what-to-install>`_ for every extra and
for upgrading from 0.17.

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
