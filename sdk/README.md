# Rhesis SDK 🧠

<meta name="google-site-verification" content="muyrLNdeOT9KjYaOnfpOmGi8K5xPe8o7r_ov3kEGdXA" />

<p align="center">
  <a href="https://github.com/rhesis-ai/rhesis/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
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

> Your team defines expectations, Rhesis generates and executes thousands of test scenarios. So that you know what you ship.

The Rhesis SDK empowers developers to programmatically access curated test sets and generate comprehensive test scenarios for Gen AI applications. Transform domain expertise into automated testing: access thousands of test scenarios, generate custom validation suites, and integrate seamlessly into your workflow to keep your Gen AI robust, reliable & compliant.

<img src="https://cdn.prod.website-files.com/68c3e3b148a4fd9bcf76eb6a/68d66fa1ff10c81d4e4e4d0f_Frame%201000004352.png"
     loading="lazy"
     width="1392"
     sizes="(max-width: 479px) 100vw, (max-width: 767px) 95vw, (max-width: 991px) 94vw, 95vw"
     alt="Rhesis Platform Results"
     srcset="https://cdn.prod.website-files.com/68c3e3b148a4fd9bcf76eb6a/68d66fa1ff10c81d4e4e4d0f_Frame%201000004352.png 2939w"
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

The Rhesis SDK provides programmatic access to the Rhesis testing platform:

- **Access Test Sets**: Browse and load curated test sets across multiple domains and use cases
- **Generate Test Scenarios**: Create custom test sets from prompts, requirements, or domain knowledge
- **Seamless Integration**: Integrate testing into your CI/CD pipeline and development workflow
- **Comprehensive Coverage**: Scale your testing from dozens to thousands of scenarios
- **Open Source**: MIT-licensed with full transparency and community-driven development

## 🚀 Installation

Install the Rhesis SDK using pip:

```bash
pip install rhesis-sdk
```

## 🐍 Python Requirements

Rhesis SDK requires **Python 3.10** or newer.

## 🏁 Getting Started

### 1. Obtain an API Key 🔑

1. Visit [https://app.rhesis.ai](https://app.rhesis.ai)
2. Sign up for a Rhesis account
3. Navigate to your account settings
4. Generate a new API key

Your API key will be in the format `rh-XXXXXXXXXXXXXXXXXXXX`. Keep this key secure and never share it publicly.

> **Note:** On the Rhesis App, you can also create test sets for your own use cases and access them via the SDK. You only need to connect your GitHub account to create a test set.

### 2. Configure  and use the SDK.


```python

from pprint import pprint

from rhesis.sdk.entities import TestSet
from rhesis.sdk.synthesizers import PromptSynthesizer

os.environ["RHESIS_API_KEY"] = "rh-your-api-key"  # Get from app.rhesis.ai settings
os.environ["RHESIS_BASE_URL"] = "https://api.rhesis.ai"  # optional

# Browse available test sets
for test_set in TestSet().all():
    pprint(test_set)

# Generate custom test scenarios
synthesizer = PromptSynthesizer(
    prompt="Generate tests for a medical chatbot that must never provide diagnosis"
)
test_set = synthesizer.generate(num_tests=10)
pprint(test_set.tests)
```

### Generating Custom Test Sets 🛠️

If none of the existing test sets fit your needs, you can generate your own. You can check out [app.rhesis.ai](http://app.rhesis.ai). There you can define requirements, scenarios and behaviors.

## 🧪 About Rhesis AI

Rhesis is an open-source testing platform that transforms how Gen AI teams validate their applications. Through collaborative test management, domain expertise becomes comprehensive automated testing: legal defines requirements, marketing sets expectations, engineers build quality, and everyone knows exactly how the Gen AI application performs before users do.

**Key capabilities:**
- **Collaborative Test Management**: Your entire team contributes requirements without writing code
- **Automated Test Generation**: Generate thousands of test scenarios from team expertise
- **Comprehensive Coverage**: Scale from dozens of manual tests to thousands of automated scenarios
- **Edge Case Discovery**: Find potential failures before your users do
- **Compliance Validation**: Ensure systems meet regulatory and ethical standards

Made in Potsdam, Germany 🇩🇪

Visit [rhesis.ai](https://rhesis.ai) to learn more about our platform and services.

## 👥 Community 💬

Join our [Discord server](https://discord.rhesis.ai) to connect with other users and developers.

## 🤗 Hugging Face

You can also find us on [Hugging Face](https://huggingface.co/rhesis). There, you can find our test sets across multiple use cases.

## 🆘 Support

For questions, issues, or feature requests:
- **Documentation**: [docs.rhesis.ai](https://docs.rhesis.ai)
- **Discord Community**: [discord.rhesis.ai](https://discord.rhesis.ai)
- **GitHub Discussions**: [Community discussions](https://github.com/rhesis-ai/rhesis/discussions)
- **Email**: hello@rhesis.ai
- **Issues**: [Report bugs or request features](https://github.com/rhesis-ai/rhesis/issues)

## 📝 License

The Rhesis SDK is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

The SDK is completely open-source and freely available for use, modification, and distribution.

---

**Made with ❤️ in Potsdam, Germany 🇩🇪**

Learn more at [rhesis.ai](https://rhesis.ai)
