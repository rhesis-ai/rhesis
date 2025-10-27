.. rhesis documentation master file, created by
   sphinx-quickstart on Sun Jan 26 17:53:53 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Rhesis SDK Documentation
========================

.. image:: https://cdn.prod.website-files.com/68c3e3b148a4fd9bcf76eb6a/68c95daec03defb40e24fca4_Rhesis%20AI_Logo_RGB_Website%20logo-p-500.png
   :alt: Rhesis Logo
   :width: 300
   :align: center

**Gen AI Testing. Collaborative. Adaptive.**

From "I hope this works" to "I know this works." Rhesis brings your whole team together—developers, domain experts, legal, and marketing—to create comprehensive testing that ensures your Gen AI applications work exactly as intended before users see them.

.. note::
   Your team defines expectations, Rhesis generates and executes thousands of test scenarios. So that you know what you ship.

🎯 Why Rhesis?
==============

**The Gen AI Testing Challenge**

Gen AI applications present unique testing challenges that traditional approaches can't handle:

- **Non-deterministic outputs**: Same input, different responses
- **Unexpected edge cases**: Unpredictable user inputs lead to problematic outputs
- **Ethical risks**: Biased, harmful, or inappropriate content generation
- **Compliance requirements**: Industry-specific regulatory standards

Traditional testing with hand-coded scenarios can't scale to unlimited user creativity. Rhesis addresses these challenges through collaborative test management that generates comprehensive automated coverage.

**Make testing a peer to development**

You've transformed your product with Gen AI, now transform how you test it. Testing deserves the same sophistication as your development tooling.

**Your whole team should define what matters**

Your legal, marketing, and domain experts know what can actually go wrong. Rhesis makes testing everyone's responsibility.

**Know what you're shipping**

The best AI teams understand their system's capabilities before release. Get complete visibility into how your Gen AI performs across thousands of real-world scenarios.

✨ Key Features
===============

- **Collaborative Test Management**: Your entire team contributes requirements, legal, compliance, marketing, domain experts, all without writing code
- **Automated Test Generation**: Automatically generate thousands of test scenarios from team expertise, requirements and existing knowledge sources
- **Comprehensive Coverage**: Scale from dozens of manual tests to thousands of automated scenarios that match your AI's complexity
- **Edge Case Discovery**: Find potential failures before your users do with sophisticated scenario generation
- **Compliance Validation**: Ensure Gen AI systems meet regulatory and ethical standards with team-defined requirements
- **Performance Analytics**: Track quality metrics over time

🚀 Quick Start
===============

Option 1: Use the Cloud Platform (Fastest)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Get started in minutes at `app.rhesis.ai <https://app.rhesis.ai>`_:

1. **Create a free account**
2. **Start generating test scenarios collaboratively**
3. **Invite your team to define requirements together**

Option 2: Use the SDK
~~~~~~~~~~~~~~~~~~~~

Install and configure the Python SDK:

.. code-block:: bash

   pip install rhesis-sdk

**Configuration:**

.. code-block:: python

   import rhesis

   rhesis.api_key = "rh-XXXXXXXXXXXXXXXXXXXX"  # Get from app.rhesis.ai settings
   rhesis.base_url = "https://api.rhesis.ai"  # optional

**Quick Example:**

.. code-block:: python

   from rhesis.sdk.entities import TestSet
   from rhesis.sdk.synthesizers import PromptSynthesizer

   # Browse available test sets
   for test_set in TestSet().all():
       print(test_set)

   # Generate custom test scenarios
   synthesizer = PromptSynthesizer(
       prompt="Generate tests for a medical chatbot that must never provide diagnosis"
   )
   test_set = synthesizer.generate(num_tests=100)

   for test in test_set.tests:
       print("-" * 40)
       print(f"Prompt: {test['prompt']['content']}")
       print(f"Behavior: {test['behavior']}")
       print(f"Category: {test['category']}")
       print(f"Topic: {test['topic']}")

Option 3: Run Locally with Docker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Clone and run the full platform locally:

.. code-block:: bash

   git clone https://github.com/rhesis-ai/rhesis.git
   cd rhesis
   docker-compose up

Visit `http://localhost:3000 <http://localhost:3000>`_ to access your local instance.

🌐 Open Source & Community-Driven
==================================

Rhesis is built by Gen AI developers who experienced inadequate testing tools firsthand. The core platform and SDK remain MIT-licensed forever, with a clear commitment: core functionality never moves to paid tiers.

Join our community:

- **Discord**: `discord.rhesis.ai <https://discord.rhesis.ai>`_
- **GitHub Discussions**: `Community discussions <https://github.com/rhesis-ai/rhesis/discussions>`_
- **Documentation**: `docs.rhesis.ai <https://docs.rhesis.ai>`_

Documentation Contents
=====================

.. toctree::
   :maxdepth: 1
   :caption: User Guide

   installation
   quickstart
   configuration

.. toctree::
   :maxdepth: 1
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
