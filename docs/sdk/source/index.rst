.. rhesis documentation master file, created by
   sphinx-quickstart on Sun Jan 26 17:53:53 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Rhesis SDK's Documentation
=====================================

.. image:: https://cdn.prod.website-files.com/66f422128b6d0f3351ce41e3/66fcfdf2e263aab9f4a19e52_Logo%20Rhesis%20Blue.png
   :alt: Rhesis Logo
   :width: 300
   :align: center

*Gen AI applications that deliver value, not surprises.*

The Rhesis SDK enables developers to access curated test sets and generate dynamic ones for GenAI applications. It provides tools to tailor validations to your needs and integrate seamlessly to keep your Gen AI robust, reliable & compliant.

Installation
===========

Install the Rhesis SDK using pip:

.. code-block:: bash

   pip install rhesis-sdk

Getting Started
==============

1. Obtain an API Key
~~~~~~~~~~~~~~~~~~~

1. Visit `Rhesis App <https://app.rhesis.ai>`_
2. Sign up for a Rhesis account
3. Navigate to your account settings
4. Generate a new API key

Your API key will be in the format ``rh-XXXXXXXXXXXXXXXXXXXX``. Keep this key secure and never share it publicly.

2. Configure the SDK
~~~~~~~~~~~~~~~~~~

You can configure the Rhesis SDK either through environment variables or direct configuration:

Using Environment Variables
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   export RHESIS_API_KEY="your-api-key"
   export RHESIS_BASE_URL="https://api.rhesis.ai"  # optional

Direct Configuration
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   import rhesis
   
   rhesis.api_key = "your-api-key"
   rhesis.base_url = "https://api.rhesis.ai"  # optional

Documentation Contents
=====================

.. toctree::
   :maxdepth: 2
   :caption: User Guide
   
   installation
   quickstart
   configuration

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   rhesis

.. toctree::
   :maxdepth: 1
   :caption: Development

   contributing
   changelog

Indices and Tables
=================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

