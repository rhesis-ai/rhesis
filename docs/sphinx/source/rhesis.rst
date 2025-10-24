Rhesis SDK API Reference
======================

This section provides detailed API documentation for the Rhesis SDK.

.. automodule:: rhesis
   :members:
   :undoc-members:
   :show-inheritance:

Core Components
--------------

Client
~~~~~~

.. autoclass:: rhesis.client.Client
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Configuration
~~~~~~~~~~~~

.. automodule:: rhesis.config
   :members:
   :undoc-members:
   :show-inheritance:

Command Line Interface
~~~~~~~~~~~~~~~~~~~~~

.. automodule:: rhesis.cli
   :members:
   :undoc-members:
   :show-inheritance:

Utilities
~~~~~~~~~

.. automodule:: rhesis.utils
   :members:
   :undoc-members:
   :show-inheritance:

Module Structure
---------------

.. toctree::
   :maxdepth: 2

   rhesis.entities
   rhesis.services
   rhesis.synthesizers

.. py:class:: rhesis.client.Client
   :noindex:

   The main client for interacting with the Rhesis API.

.. py:class:: rhesis.services.llm.Client
   :noindex:

   A client for interacting with language models.
