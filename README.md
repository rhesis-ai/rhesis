# Rhesis: Made for Gen AI Teams 🫶
<p align="center">
  <a href="https://github.com/rhesis-ai/rhesis/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/rhesis-ai/rhesis" alt="License">
  </a>
  <a href="https://pypi.org/project/rhesis-sdk/">
    <img src="https://img.shields.io/pypi/v/rhesis-sdk" alt="PyPI Version">
  </a>
  <a href="https://pypi.org/project/rhesis-sdk/">
    <img src="https://img.shields.io/pypi/pyversions/rhesis-sdk" alt="Python Versions">
  </a>
  <a href="https://codecov.io/gh/rhesis-ai/rhesis">
    <img src="https://codecov.io/gh/rhesis-ai/rhesis/graph/badge.svg?token=1XQV983JEJ" alt="codecov">
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

> Comprehensive test management for Gen AI applications

Rhesis is a complete test management platform for Gen AI teams, helping you build applications that deliver value, not surprises. The platform provides tools to create, manage, and execute test cases specifically designed for generative AI applications, ensuring they remain robust, reliable, and compliant.

<img src="https://cdn.prod.website-files.com/66f422128b6d0f3351ce41e3/67ea61119543db5f3fa4776e_Screenshot%20Rhesis%20AI%20Platform.png" 
     loading="lazy" 
     width="1392" 
     sizes="(max-width: 479px) 100vw, (max-width: 767px) 95vw, (max-width: 991px) 94vw, 95vw" 
     alt="Dashboard mockup" 
     srcset="https://cdn.prod.website-files.com/66f422128b6d0f3351ce41e3/67ea61119543db5f3fa4776e_Screenshot%20Rhesis%20AI%20Platform.png 2939w" 
     class="uui-layout41_lightbox-image-01-2">

## ✨ Key Features

- **Test Set Management**: Create, organize, and maintain comprehensive test suites for Gen AI applications
- **Automated Test Generation**: Generate test cases automatically based on your application's requirements
- **Edge Case Discovery**: Identify potential vulnerabilities and edge cases in your Gen AI systems
- **Compliance Validation**: Ensure your AI systems meet regulatory and ethical standards
- **Integration Capabilities**: Seamlessly integrate testing into your development workflow
- **Performance Tracking**: Monitor and analyze test results over time to track improvements

## 🌐 Open Source Philosophy

Rhesis is proudly open source, built on the belief that responsible AI testing should be accessible to everyone:

- **Community-Driven Development**: We believe the best tools are built collaboratively with input from diverse perspectives
- **Transparency First**: All our algorithms and methodologies are open for inspection and improvement
- **Extensible Architecture**: Build your own plugins, extensions, and integrations on top of our platform
- **Free Core Functionality**: Essential testing capabilities are free and open source forever
- **Democratizing AI Safety**: Making robust AI testing accessible to teams of all sizes, not just large corporations
- **Research Collaboration**: We actively collaborate with academic institutions to advance the field of AI testing
- **Public Test Sets**: We maintain a growing library of open source test sets for common AI failure modes

Our commitment to open source goes beyond code. We're building an ecosystem where knowledge about AI testing is shared freely, helping the entire industry build safer, more reliable AI systems.

### Commercial vs. Open Source

While we offer commercial services built on top of Rhesis, we maintain a clear separation between open source and commercial offerings:

- The core platform and SDK remain MIT-licensed and free forever
- Commercial offerings focus on enterprise support, managed services, and specialized integrations
- Improvements developed for commercial clients are contributed back to the open source codebase whenever possible
- We never "bait and switch" by moving core functionality from open source to paid tiers
- All commercial/enterprise code is clearly separated in dedicated `ee/` folders and not mixed with open source code

## 📑 Repository Structure

This main repo contains all the components of the Rhesis platform:

```
rhesis/
├── apps/
│   ├── backend/       # FastAPI backend service
│   ├── frontend/      # React frontend application
│   ├── worker/        # Celery worker service
│   ├── chatbot/       # Chatbot application
│   └── polyphemus/    # Uncensored LLM service for test generation
├── sdk/               # Python SDK for Rhesis
├── infrastructure/    # Infrastructure as code
├── scripts/           # Utility scripts
└── docs/              # Documentation
```

## 🚀 Getting Started

Please refer to the README files in each component directory for specific setup instructions:

- [Backend](apps/backend/README.md)
- [Frontend](apps/frontend/README.md)
- [SDK](sdk/README.md)
- [Worker](apps/worker/README.md)
- [Chatbot](apps/chatbot/README.md)
- [Polyphemus](apps/polyphemus/README.md)

### Using the SDK

Install the Rhesis SDK using pip:

```bash
pip install rhesis-sdk
```

#### Obtain an API Key 🔑

1. Visit [https://app.rhesis.ai](https://app.rhesis.ai)
2. Sign up for a Rhesis account
3. Navigate to your account settings
4. Generate a new API key

Your API key will be in the format `rh-XXXXXXXXXXXXXXXXXXXX`. Keep this key secure and never share it publicly.

> **Note:** You can create custom test sets for your specific use cases directly in the Rhesis App by connecting your GitHub account.

#### Configure the SDK ⚙️

You can configure the Rhesis SDK either through environment variables or direct configuration:

```bash
export RHESIS_API_KEY="your-api-key"
export RHESIS_BASE_URL="https://api.rhesis.ai"  # optional
```

Or in Python:

```python
import rhesis 

# Set configuration directly
rhesis.base_url = "https://api.rhesis.ai"  # optional
rhesis.api_key = "rh-XXXXXXXXXXXXXXXXXXXX"
```

## 📦 Components

### Backend

The backend service provides the core API for the platform, handling authentication, test set management, and integration with external services.

### Frontend

The frontend application provides the user interface for creating, managing, and analyzing test sets for Gen AI applications.

### SDK

The SDK enables developers to access curated test sets and generate dynamic ones for GenAI applications.

#### SDK Features

- **List Test Sets**: Browse through available curated test sets
- **Load Test Sets**: Load specific test sets for your use case
- **Download Test Sets**: Download test set data for offline use
- **Generate Test Sets**: Generate new test sets from basic prompts

#### Quick Example

```python
from rhesis.sdk.entities import TestSet

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

### Worker

The worker service handles background tasks such as test set generation and analysis.

### Chatbot

The chatbot application provides a conversational interface for interacting with the platform.

### Polyphemus

Polyphemus is a service with an uncensored LLM specifically designed for comprehensive test generation. It enables the creation of robust test cases by exploring edge cases and potential vulnerabilities that might be filtered by standard, safety-constrained models.

## 🔄 Versioning and Tagging Strategy

Each component in this monorepo maintains its own version number following [Semantic Versioning](https://semver.org/). We use a component-specific tagging strategy for releases:

- `backend-v1.0.0` - For backend releases
- `frontend-v2.3.1` - For frontend releases
- `sdk-v0.5.2` - For SDK releases

For more details on our versioning and release process, please see [CONTRIBUTING.md](CONTRIBUTING.md#versioning-and-release-process).

## 👥 Contributing

We welcome contributions to the Rhesis platform! Rhesis thrives thanks to our amazing community of contributors.

### Ways to Contribute

- **Code**: Fix bugs, implement features, or improve documentation
- **Test Sets**: Contribute new test cases or improve existing ones
- **Documentation**: Help improve our guides, tutorials, and API references
- **Community Support**: Answer questions in our Discord or GitHub discussions
- **Feedback**: Report bugs, suggest features, or share your experience using Rhesis

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write or update tests
5. Submit a pull request

Our team reviews PRs regularly and provides feedback. We follow a code of conduct to ensure a welcoming environment for all contributors.

For detailed guidelines, please see [CONTRIBUTING.md](CONTRIBUTING.md).

### 🚀 Releases

For information about releasing Rhesis components and platform versions, see our [Release Guide](RELEASING.md).

### Community Meetings

We host community calls where we discuss roadmap, feature requests, and showcase community contributions. Join our Discord server for announcements.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For questions, issues, or feature requests:
- Visit our [documentation](https://docs.rhesis.ai)
- Join our [Discord server](https://discord.rhesis.ai)
- Contact us at hello@rhesis.ai
- Create an issue in this repository

### Community Resources

- **[GitHub Discussions](https://github.com/rhesis-ai/rhesis/discussions)**: For questions, ideas, and community discussions

## 🧠 Why Test Gen AI Applications?

Testing generative AI applications presents unique challenges compared to traditional software:

- **Non-deterministic outputs**: Gen AI can produce different responses to the same input
- **Hallucinations**: Models may generate plausible but factually incorrect information
- **Edge cases**: Unexpected inputs can lead to problematic outputs
- **Ethical concerns**: Models may produce biased, harmful, or inappropriate content
- **Compliance requirements**: Many industries have specific regulatory requirements

Rhesis provides the tools to address these challenges through comprehensive test management, helping teams build more reliable and trustworthy Gen AI applications.

Made in Potsdam, Germany 🇩🇪

Visit [rhesis.ai](https://rhesis.ai) to learn more. 