Quickstart
==========

This guide will help you get started with the Rhesis SDK quickly.

Setup
-----

First, make sure you have installed the Rhesis SDK:

.. code-block:: bash

   pip install rhesis-sdk

Then, configure your API key:

.. code-block:: python

   import rhesis

   rhesis.api_key = "your-api-key"  # Replace with your actual API key

Basic Usage
----------

Here's a simple example showing how to use the Rhesis SDK to evaluate a model's response:

.. code-block:: python

   import rhesis

   # Set up your API key if not already done
   rhesis.api_key = "your-api-key"

   # Define a test case
   test_case = {
       "prompt": "Explain the concept of quantum computing in simple terms",
       "expected_properties": {
           "accurate": True,
           "toxicity": False,
           "readability_level": "beginner"
       }
   }

   # Evaluate a model's response
   response = "Quantum computing uses quantum bits or 'qubits' that can be both 0 and 1 at the same time, unlike classical bits. This allows quantum computers to process certain types of problems much faster than regular computers."

   # Submit for evaluation
   result = rhesis.Evaluation.create(
       test_case=test_case,
       actual_response=response
   )

   # Print the evaluation results
   print(result)

Creating Test Sets
-----------------

You can create and manage test sets for consistent evaluations:

.. code-block:: python

   # Create a test set
   test_set = rhesis.TestSet.create(
       name="Basic QA Test Set",
       description="Tests for question-answering capabilities"
   )

   # Add test cases to the test set
   test_case = rhesis.TestCase.create(
       test_set_id=test_set.id,
       prompt="What is machine learning?",
       expected_properties={
           "accurate": True,
           "comprehensive": True
       }
   )

Next Steps
---------

Explore the full documentation to learn about:

* Advanced evaluation options
* Custom validation rules
* Batch processing
* Integration with CI/CD pipelines
