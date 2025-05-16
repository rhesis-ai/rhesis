# Rhesis SDK 🧠
<meta name="google-site-verification" content="muyrLNdeOT9KjYaOnfpOmGi8K5xPe8o7r_ov3kEGdXA" />
<p align="center">
  <img src="https://cdn.prod.website-files.com/66f422128b6d0f3351ce41e3/66fcfdf2e263aab9f4a19e52_Logo%20Rhesis%20Blue.png" alt="Rhesis Blue" width="300"/>
</p>
<p align="center">
  <a href="https://github.com/rhesis-ai/rhesis-sdk/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/rhesis-ai/rhesis-sdk" alt="License">
  </a>
  <a href="https://pypi.org/project/rhesis-sdk/">
    <img src="https://img.shields.io/pypi/v/rhesis-sdk" alt="PyPI Version">
  </a>
  <a href="https://pypi.org/project/rhesis-sdk/">
    <img src="https://img.shields.io/pypi/pyversions/rhesis-sdk" alt="Python Versions">
  </a>
  <a href="https://discord.rhesis.ai">
    <img src="https://img.shields.io/discord/1340989671601209408?color=7289da&label=Discord&logo=discord&logoColor=white" alt="Discord">
  </a>
  <a href="https://www.linkedin.com/company/rhesis-ai">
    <img src="https://img.shields.io/badge/LinkedIn-Rhesis_AI-blue?logo=linkedin" alt="LinkedIn">
  </a>
  <a href="https://huggingface.co/rhesis">
    <img src="https://img.shields.io/badge/🤗-Rhesis-yellow" alt="Hugging Face">
  </a>
  <a href="https://docs.rhesis.ai">
    <img src="https://img.shields.io/badge/docs-rhesis.ai-blue" alt="Documentation">
  </a>
</p>

> Gen AI applications that deliver value, not surprises.

The Rhesis SDK enables developers to access curated test sets and generate dynamic ones for GenAI applications. It provides tools to tailor validations to your needs and integrate seamlessly to keep your Gen AI robust, reliable & compliant.

<img src="https://cdn.prod.website-files.com/66f422128b6d0f3351ce41e3/67ea61119543db5f3fa4776e_Screenshot%20Rhesis%20AI%20Platform.png" 
     loading="lazy" 
     width="1392" 
     sizes="(max-width: 479px) 100vw, (max-width: 767px) 95vw, (max-width: 991px) 94vw, 95vw" 
     alt="Dashboard mockup" 
     srcset="https://cdn.prod.website-files.com/66f422128b6d0f3351ce41e3/67ea61119543db5f3fa4776e_Screenshot%20Rhesis%20AI%20Platform.png 2939w" 
     class="uui-layout41_lightbox-image-01-2">

## 📑 Table of Contents

- [Features](#-features)
- [Installation](#-installation)
- [Getting Started](#-getting-started)
  - [Obtain an API Key](#1-obtain-an-api-key-)
  - [Configure the SDK](#2-configure-the-sdk-%EF%B8%8F)
- [Quick Start](#-quick-start)
  - [Working with Test Sets](#working-with-test-sets-)
  - [Generating Custom Test Sets](#generating-custom-test-sets-%EF%B8%8F)
- [About Rhesis AI](#-about-rhesis-ai)
- [Community](#-community-)
- [Hugging Face](#-hugging-face)
- [Support](#-support)
- [License](#-license)

## ✨ Features

The Rhesis SDK currently provides functionality to work with Rhesis test sets through routine operations:

- **List Test Sets**: Browse through available curated test sets
- **Load Test Sets**: Load specific test sets for your use case
- **Download Test Sets**: Download test set data for offline use
- **Generate Test Sets**: Generate new test sets from basic prompts

## 🚀 Installation

Install the Rhesis SDK using pip:

```bash
pip install rhesis-sdk
```

## 🏁 Getting Started

### 1. Obtain an API Key 🔑

1. Visit [https://app.rhesis.ai](https://app.rhesis.ai)
2. Sign up for a Rhesis account
3. Navigate to your account settings
4. Generate a new API key

Your API key will be in the format `rh-XXXXXXXXXXXXXXXXXXXX`. Keep this key secure and never share it publicly.

> **Note:** On the Rhesis App, you can also create test sets for your own use cases and access them via the SDK. You only need to connect your GitHub account to create a test set.

### 2. Configure the SDK ⚙️

You can configure the Rhesis SDK either through environment variables or direct configuration:

#### Using Environment Variables

```bash
export RHESIS_API_KEY="your-api-key"
export RHESIS_BASE_URL="https://api.rhesis.ai"  # optional
```

#### Direct Configuration

```python
import rhesis 

# Set configuration directly
rhesis.base_url = "https://api.rhesis.ai"  # optional
rhesis.api_key = "rh-XXXXXXXXXXXXXXXXXXXX"
```

## ⚡ Quick Start

Before you start, you can configure the Rhesis SDK either through environment variables or direct configuration, as described above.

### Working with Test Sets 📋

```python
from rhesis.entities import TestSet

# List all test sets
for test_set in TestSet().all():
    print(test_set)

# Load a specific test set
test_set = TestSet(id="agent-or-industry-fraud-harmful")
test_set.load()

# Download test set data
test_set.download()

# Generate a new test set
prompt_synthesizer = PromptSynthesizer(prompt="Generate tests for an insurance chatbot that can answer questions about the company's policies.")
test_set = prompt_synthesizer.generate(num_tests=5)

```

For more detailed examples, check out our [example notebooks](examples/).

### Generating Custom Test Sets 🛠️

If none of the existing test sets fit your needs, you can generate your own.

You can check out [app.rhesis.ai](http://app.rhesis.ai). There you can define requirements, scenarios and personas, and even import your existing GitHub repository.

## 🧪 About Rhesis AI

Rhesis AI helps organizations build Gen AI applications that deliver value, not surprises. Our platform enables you to:
- Access curated test sets
- Generate custom test sets
- Upload your custom test sets to the cloud
- Tailor validations to your specific needs
- Integrate testing seamlessly into your workflow
- Keep your Gen AI applications robust, reliable & compliant

Made in Potsdam, Germany 🇩🇪

Visit [rhesis.ai](https://rhesis.ai) to learn more about our platform and services.

## 👥 Community 💬

Join our [Discord server](https://discord.rhesis.ai) to connect with other users and developers.

## 🤗 Hugging Face

You can also find us on [Hugging Face](https://huggingface.co/rhesis). There, you can find our test sets across multiple use cases.

## 🆘 Support

For questions, issues, or feature requests:
- Visit our [documentation](https://docs.rhesis.ai)
- Contact us at hello@rhesis.ai
- Create an issue in this repository

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
