Configuration
=============

This page explains the various configuration options available for the Rhesis SDK.

API Key
-------

The Rhesis SDK requires an API key to authenticate with the Rhesis API. You can obtain an API key by signing up at `Rhesis App <https://app.rhesis.ai>`_.

There are two ways to configure your API key:

Using Environment Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~

Set the following environment variables:

.. code-block:: bash

   export RHESIS_API_KEY="your-api-key"
   export RHESIS_BASE_URL="https://api.rhesis.ai"  # optional, defaults to this value

Direct Configuration
~~~~~~~~~~~~~~~~~~~

Configure directly in your Python code:

.. code-block:: python

   import rhesis

   rhesis.api_key = "your-api-key"
   rhesis.base_url = "https://api.rhesis.ai"  # optional, defaults to this value

Advanced Configuration
---------------------

Timeout Settings
~~~~~~~~~~~~~~~

You can configure request timeouts:

.. code-block:: python

   rhesis.timeout = 30  # Set timeout to 30 seconds

Retry Settings
~~~~~~~~~~~~~

Configure automatic retries for failed API requests:

.. code-block:: python

   rhesis.max_retries = 3  # Number of retry attempts
   rhesis.retry_delay = 1  # Delay between retries in seconds

Proxy Configuration
~~~~~~~~~~~~~~~~~

If you need to use a proxy server:

.. code-block:: python

   rhesis.proxy = {
       "http": "http://user:pass@10.10.1.10:3128/",
       "https": "http://user:pass@10.10.1.10:1080/"
   }

Logging
-------

The Rhesis SDK uses Python's standard logging module. You can configure it like this:

.. code-block:: python

   import logging

   # Configure logging
   logging.basicConfig(level=logging.INFO)

   # Or for more detailed logging
   logging.getLogger("rhesis").setLevel(logging.DEBUG)
