# Rhesis: Open-Source Gen AI Testing ![Rhesis AI_Logo_RGB_Favicon](https://github.com/user-attachments/assets/ff43ca6a-ffde-4aff-9ff9-eec3897d0d02)

<p align="center">
  <a href="https://github.com/rhesis-ai/rhesis/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT%20%2B%20Commercial-blue" alt="License">
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

> Your team defines expectations, Rhesis generates and executes thousands of test scenarios. So that you know what you ship.

Rhesis is an open-source testing platform that transforms how Gen AI teams validate their applications. Collaborative test management turns domain expertise into comprehensive automated testing: legal defines requirements, marketing sets expectations, engineers build quality, and everyone knows exactly how the Gen AI application performs before users do.

<img src="https://cdn.prod.website-files.com/68c3e3b148a4fd9bcf76eb6a/69039cdfccde6a7b02eac36f_Release%200.4.1.gif"
     loading="lazy"
     width="1080"
     sizes="(max-width: 479px) 100vw, (max-width: 767px) 95vw, (max-width: 991px) 94vw, 95vw"
     alt="Rhesis Platform Results"
     srcset="https://cdn.prod.website-files.com/68c3e3b148a4fd9bcf76eb6a/69039cdfccde6a7b02eac36f_Release%200.4.1.gif 1080w"
     >

## 🎯 Why Rhesis?

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

## ✨ Key Features

- **Collaborative Test Management**: Your entire team contributes requirements, legal, compliance, marketing, domain experts, all without writing code
- **Automated Test Generation**: Automatically generate thousands of test scenarios from team expertise, requirements and existing knowledge sources
- **Comprehensive Coverage**: Scale from dozens of manual tests to thousands of automated scenarios that match your AI's complexity
- **Edge Case Discovery**: Find potential failures before your users do with sophisticated scenario generation
- **Compliance Validation**: Ensure Gen AI systems meet regulatory and ethical standards with team-defined requirements
- **Performance Analytics**: Track quality metrics over time

## 🌐 Open Source & Community-Driven

Rhesis is built by Gen AI developers who experienced inadequate testing tools firsthand. The core platform and SDK remain MIT-licensed forever, with a clear commitment: core functionality never moves to paid tiers. All commercial code lives in dedicated `ee/` folders.

Join our community calls to discuss roadmap, features, and contributions. Connect via [Discord](https://discord.rhesis.ai) for announcements.

## 📑 Repository Structure

This monorepo contains the complete Rhesis ecosystem:

```
rhesis/
├── apps/
│   ├── backend/       # FastAPI backend service
│   ├── frontend/      # React frontend application
│   ├── worker/        # Celery worker for background tasks
│   ├── chatbot/       # Conversational testing interface
│   └── polyphemus/    # Uncensored LLM for comprehensive test generation
├── sdk/               # Python SDK for Rhesis
├── infrastructure/    # Infrastructure as code
├── scripts/           # Utility scripts
└── docs/              # Documentation
```

## 🚀 Quick Start

### Option 1: Use the cloud platform (fastest)

Get started in minutes at [app.rhesis.ai](https://app.rhesis.ai):

1. Create a free account
2. Start generating test scenarios collaboratively
3. Invite your team to define requirements together

### Option 2: Use the SDK

Install and configure the Python SDK:

```bash
pip install rhesis-sdk
```

```python
import rhesis

rhesis.api_key = "rh-XXXXXXXXXXXXXXXXXXXX"  # Get from app.rhesis.ai settings
rhesis.base_url = "https://api.rhesis.ai"  # optional
```

**Quick example:**

```python
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
```

### Option 3: Run locally with Docker

Clone and run the full platform locally:

```bash
git clone https://github.com/rhesis-ai/rhesis.git
cd rhesis
docker-compose up
```

Visit `http://localhost:3000` to access your local instance.

**Detailed setup instructions:** See component READMEs in [Component Documentation](#-component-documentation).


## 👥 Contributing

Rhesis thrives thanks to our community. Here's how you can contribute:

### Ways to Contribute

- **Code**: Fix bugs, implement features, improve performance
- **Test Sets**: Contribute test cases for common AI failure modes
- **Documentation**: Enhance guides, tutorials, and API references
- **Community Support**: Help others in Discord or GitHub discussions
- **Feedback**: Report bugs, request features, share your experience

### Contributing Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Commit with clear messages
5. Push and open a pull request

We review PRs regularly and maintain a welcoming environment through our code of conduct.

**Detailed guidelines:** [CONTRIBUTING.md](CONTRIBUTING.md)
**Release process:** [RELEASING.md](RELEASING.md)

## 📝 License

**Community Edition**: MIT License - see [LICENSE](LICENSE) file for details.

**Enterprise Edition**: Enterprise features located in `ee/` folders are subject to separate commercial licenses. Contact hello@rhesis.ai for enterprise licensing information.

## 🆘 Support

- **Documentation**: [docs.rhesis.ai](https://docs.rhesis.ai)
- **Discord Community**: [discord.rhesis.ai](https://discord.rhesis.ai)
- **GitHub Discussions**: [Community discussions](https://github.com/rhesis-ai/rhesis/discussions)
- **Email**: hello@rhesis.ai
- **Issues**: [Report bugs or request features](https://github.com/rhesis-ai/rhesis/issues)

---

**Made with ![Rhesis AI_Logo_RGB_Favicon](https://github.com/user-attachments/assets/598c2d81-572c-46bd-b718-dee32cdc749c)
 in Potsdam,<?xml version="1.0" encoding="UTF-8"?>
<svg id="Layer_1" data-name="Layer 1" xmlns="http://www.w3.org/2000/svg" width="32" height="32" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 32 32">
  <defs>
    <clipPath id="clippath">
      <circle cx="16" cy="16" r="16" fill="none"/>
    </clipPath>
  </defs>
  <circle cx="16" cy="16" r="16" fill="#fff"/>
  <g clip-path="url(#clippath)">
    <g>
      <path d="M13.29,14.51s0,0,0,0c0,0-.01,0-.02,0,0,0,0,0,.01,0,0,0,0,0,0,0Z" fill="none"/>
      <path d="M11.98,12.23s0,0,0-.01c0,0,0,0,0,.01Z" fill="none"/>
      <path d="M11.89,14.48s0-.04-.01-.07c0,.02,0,.04.01.07Z" fill="none"/>
      <path d="M14.75,13.93s0,0,0,0c0,0,.01,0,.02-.01,0,0,0,0-.01,0,0,0,0,0,0,0Z" fill="none"/>
      <path d="M15.98,12.94s0,0,0,0c0,0-.13.1-.19.15-.04.04-.11.1-.2.17.08-.07.15-.13.19-.16.06-.05.19-.15.19-.15,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0Z" fill="none"/>
      <path d="M13.71,14.42s.02,0,.04,0c0,0-.02,0-.03,0,0,0,0,0,0,0Z" fill="none"/>
      <path d="M12.13,11.98s.02-.03.04-.04c-.01.01-.02.03-.04.04Z" fill="none"/>
      <path d="M12.04,12.11s.01-.02.02-.04c0,.01-.01.02-.02.04Z" fill="none"/>
      <path d="M11.81,14.61s.05,0,.08,0c.01,0,.02,0,.02,0,0,0,0,0,0,0,0,0,0,0,0,0h0s0,0,.01,0c0,0,0,0,0,0,.02,0,.04,0,.07,0,.02,0,.03,0,.05,0-.08,0-.13,0-.13,0-.04,0-.07,0-.11,0Z" fill="none"/>
      <path d="M11.87,14.39c-.02-.1-.03-.22-.05-.36.01.13.03.25.05.36Z" fill="none"/>
      <path d="M11.82,13.98s0-.05,0-.07c0,.02,0,.05,0,.07Z" fill="none"/>
      <path d="M25.33,6.1c.01.23.03.48.05.76-.03-.28-.04-.53-.05-.76Z" fill="none"/>
      <path d="M18.04,11.9s-.06,0-.09,0c.03,0,.06,0,.09,0Z" fill="#97d5ee"/>
      <path d="M18.69,12.1s-.03-.02-.05-.04c.02.01.03.02.05.04Z" fill="#97d5ee"/>
      <path d="M17.81,11.9s-.06,0-.09,0c.03,0,.06,0,.09,0Z" fill="#97d5ee"/>
      <path d="M18.21,11.92s-.04,0-.06,0c.02,0,.04,0,.06,0Z" fill="#97d5ee"/>
      <path d="M18.13,11.91s-.06,0-.09,0c.03,0,.06,0,.09,0Z" fill="#97d5ee"/>
      <path d="M18.63,12.05s-.03-.02-.05-.03c.02,0,.04.02.05.03Z" fill="#97d5ee"/>
      <path d="M16.95,12.09s-.05.03-.08.05c.03-.02.05-.03.08-.05Z" fill="#97d5ee"/>
      <path d="M17.17,11.99s-.05.02-.08.03c.03,0,.05-.02.08-.03Z" fill="#97d5ee"/>
      <path d="M18.46,11.97s0,0,0,0c0,0,0,0,0,0Z" fill="#97d5ee"/>
      <path d="M17.43,11.93s-.05,0-.08.01c.03,0,.05-.01.08-.01Z" fill="#97d5ee"/>
      <path d="M17.05,12.04s-.04.02-.07.03c.02-.01.04-.02.07-.03Z" fill="#97d5ee"/>
      <path d="M17.7,11.9s-.07,0-.11,0c.04,0,.07,0,.11,0Z" fill="#97d5ee"/>
      <path d="M17.56,11.91s-.05,0-.08,0c.03,0,.05,0,.08,0Z" fill="#97d5ee"/>
      <path d="M17.32,11.95s-.07.02-.11.03c.04-.01.07-.02.11-.03Z" fill="#97d5ee"/>
      <path d="M18.99,12.92c.01-.24-.03-.54-.23-.76.2.21.24.51.23.76-.03,2.14.38,3.11,1,3.72.05.05.11.1.16.15-.06-.05-.11-.09-.16-.15-.62-.61-1.03-1.58-1-3.72Z" fill="#97d5ee"/>
      <path d="M25.38,6.86c-.02-.28-.04-.53-.05-.76-1.26.02-2.55.33-3.82.91-1.68.76-2.96,1.62-4.09,3.49,2.65.07,5.81.18,8.62.29-.35-1.4-.56-2.83-.66-3.93Z" fill="#97d5ee"/>
      <path d="M18.5,11.98s.04.02.05.02c0,0-.01,0-.02-.01-.01,0-.02,0-.03-.01Z" fill="#97d5ee"/>
      <path d="M26.58,12.47c-.37.17-.64.39-.76.68-.36.89-.2,2.64-1.18,3.48-.46.4-1.54,1.04-3.19.73-.23-.04-.47-.1-.68-.21-.14-.07-.15-.07-.21-.1-.65,1.65-2.22,2.78-3.76,3.56.08.25.17.49.27.74,1.9,4.35,6.34,6.11,8.19,6.67.48.15,1,.08,1.42-.2,2.79-1.84,5.03-4.46,6.4-7.54-3.36-1.44-5.29-4.45-6.49-7.81Z" fill="#97d5ee"/>
      <path d="M18.22,11.92s.02,0,.03,0c0,0,0,0-.01,0,0,0-.01,0-.02,0Z" fill="#97d5ee"/>
      <path d="M20.34,16.92s-.09-.07-.14-.1c.05.04.09.07.14.1Z" fill="#97d5ee"/>
      <path d="M18.76,12.16s-.03-.03-.05-.04c.02.01.03.03.05.04Z" fill="#97d5ee"/>
      <path d="M17.85,11.9s.05,0,.07,0c-.02,0-.05,0-.07,0Z" fill="#97d5ee"/>
      <path d="M26.58,12.48c1.21,3.36,3.14,6.36,6.49,7.81.7-1.57,1.17-3.27,1.38-5.05.11-.94,0-1.89-.31-2.78h0c-.81-.15-5.61-.85-7.56.02Z" fill="#50b9e0"/>
      <path d="M26.04,10.79c4.1.16,7.48.32,7.54.33-.85-1.73-1.93-2.72-3.33-3.67-1.49-1-3.3-1.37-4.91-1.35.01.23.03.48.05.76.1,1.1.31,2.53.66,3.93Z" fill="#50b9e0"/>
      <polygon points="11.91 14.61 11.91 14.61 11.91 14.61 11.91 14.61 11.91 14.61" fill="#fdd803"/>
      <path d="M11.91,14.61s0,0,.01,0c0,0,0,0-.01,0,0,0,0,0,0,0Z" fill="#fdd803"/>
      <path d="M13.27,14.51s-.01,0-.02,0c.01,0,.02,0,.03,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0-.01,0Z" fill="#fdd803"/>
      <path d="M13.74,14.42s-.02,0-.04,0c-.01,0-.02,0-.04,0-.12.03-.25.05-.38.07,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,.17-.03.34-.06.49-.1,0,0-.02,0-.03,0,0,0,0,0,0,0Z" fill="#fdd803"/>
      <path d="M14.56,14.06s-.02.01-.02.02c.07-.04.14-.09.21-.14,0,0,0,0,0,0,0,0,0,0,0,0-.06.05-.13.09-.19.13Z" fill="#fdd803"/>
      <path d="M20.56,17.06c-.06-.03-.12-.07-.18-.11-.01,0-.03-.02-.04-.03-.05-.03-.09-.07-.14-.1-.01-.01-.03-.02-.04-.03-.06-.05-.11-.09-.16-.15-.62-.61-1.03-1.58-1-3.72.01-.24-.03-.54-.23-.76,0,0,0,0,0,0-.01-.02-.03-.03-.05-.04,0,0-.01,0-.02-.01-.02-.01-.03-.02-.05-.04,0,0-.01,0-.02-.01-.02-.01-.03-.02-.05-.03,0,0-.02,0-.03-.01-.02,0-.04-.02-.05-.02-.01,0-.02-.01-.04-.01,0,0,0,0,0,0-.07-.02-.13-.04-.2-.04,0,0-.02,0-.03,0,0,0,0,0-.01,0-.02,0-.04,0-.06,0,0,0-.01,0-.02,0-.03,0-.06,0-.09,0,0,0,0,0,0,0-.03,0-.06,0-.09,0,0,0-.02,0-.03,0-.02,0-.05,0-.07,0-.01,0-.02,0-.03,0-.03,0-.06,0-.09,0,0,0-.01,0-.02,0-.04,0-.07,0-.11,0-.01,0-.02,0-.04,0-.03,0-.05,0-.08,0-.01,0-.03,0-.04,0-.03,0-.05,0-.08.01-.01,0-.03,0-.04,0-.04,0-.07.02-.11.03-.01,0-.02,0-.03.01-.03,0-.05.02-.08.03-.01,0-.03.01-.04.02-.02,0-.04.02-.07.03-.01,0-.03.01-.04.02-.03.01-.05.03-.08.05,0,0-.01,0-.02.01-.16.11-.8.73-.87.8,0,0,0,0,0,0,0,0,0,0,0,0,0,0-.13.1-.19.15-.04.04-.11.1-.19.16-.21.18-.53.44-.84.65,0,0-.01,0-.02.01,0,0,0,0,0,0-.07.05-.14.1-.21.14-.25.17-.42.26-.75.34-.15.04-.32.07-.49.1,0,0,0,0,0,0-.01,0-.02,0-.03,0-.37.06-.95.09-1.21.1-.02,0-.03,0-.05,0-.02,0-.04,0-.07,0,0,0,0,0,0,0,0,0,0,0-.01,0h0s0,0,0,0c0,0-.01,0-.02,0-.03,0-.05,0-.08,0-.03,0-.05,0-.08,0-.27,0-.52,0-.74,0-.07,0-.13,0-.19,0-.12,0-1.76-.04-2.35-.06-1.1-.04-2.24-.09-3.37.04-2.25.27-3.62,1.1-4.08,2.47-.36,1.07.02,2.38.97,3.34,1.51,1.53,4.12,2.27,6.03,2.27,3.15.01,5.05-.54,6.42-1.05.68-.25,1.52-.57,2.37-1,1.54-.78,3.1-1.9,3.76-3.56ZM4.49,18.5c-.57,0-1.03-.26-1.03-.57s.46-.57,1.03-.57,1.03.26,1.03.57-.46.57-1.03.57ZM7.5,20.16c-.57,0-1.03-.26-1.03-.57s.46-.57,1.03-.57,1.03.26,1.03.57-.46.57-1.03.57Z" fill="#fdd803"/>
      <path d="M11.91,14.61s0-.05-.02-.13c0-.02,0-.04-.01-.07,0,0,0-.02,0-.03-.02-.11-.03-.23-.05-.36,0-.02,0-.03,0-.05,0-.02,0-.05,0-.07-.05-.52-.05-1.21.16-1.68,0,0,0,0,0-.01.02-.04.04-.07.06-.1,0-.01.01-.02.02-.04.02-.03.04-.06.07-.09.01-.01.02-.03.04-.04.03-.03.06-.06.09-.08.2-.16.57-.25.99-.3l.36-.03c.16-.01.31-.02.45-.02,1.94,0,1.95,1.13,1.93,1.38,0,.01,0,.02,0,.03,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,.07-.07.7-.69.87-.8,0,0,.01,0,.02-.01.03-.02.05-.03.08-.05.01,0,.03-.01.04-.02.02-.01.04-.02.07-.03.01,0,.03-.01.04-.02.03,0,.05-.02.08-.03.01,0,.02,0,.03-.01.04-.01.07-.02.11-.03.01,0,.03,0,.04,0,.03,0,.05-.01.08-.01.01,0,.03,0,.04,0,.03,0,.05,0,.08,0,.01,0,.02,0,.04,0,.04,0,.07,0,.11,0,0,0,.01,0,.02,0,.03,0,.06,0,.09,0,.01,0,.02,0,.03,0,.03,0,.05,0,.07,0,.01,0,.02,0,.03,0,.03,0,.06,0,.09,0,0,0,0,0,0,0,.03,0,.06,0,.09,0,0,0,.01,0,.02,0,.02,0,.04,0,.06,0,0,0,0,0,.01,0,0,0,.01,0,.02,0,0,0,0,0,.01,0,.07,0,.14.02.2.04,0,0,0,0,0,0,.01,0,.02,0,.04.01.01,0,.02,0,.03.01,0,0,.01,0,.02.01,0,0,.02,0,.03.01.02,0,.04.02.05.03,0,0,.01,0,.02.01.02.01.03.02.05.04,0,0,.01,0,.02.01.02.01.03.03.05.04,0,0,0,0,0,0,.2.21.24.51.23.76-.03,2.14.38,3.11,1,3.72.05.05.11.1.16.15.01.01.03.02.04.03.05.04.09.07.14.1.01,0,.03.02.04.03.13.08.26.15.39.22.22.1.45.16.68.21,1.65.31,2.73-.33,3.19-.73.97-.84.82-2.59,1.18-3.48.12-.29.39-.52.76-.68,1.95-.87,6.75-.17,7.56-.03,0,0,0,0,0,0,0,0-.1-.3-.27-.7-.02-.04-.03-.08-.05-.12-.06-.14-.13-.28-.2-.45-.01-.02-.02-.04-.03-.07,0,0,0,0,0,0-.05-.01-3.43-.17-7.54-.33-2.81-.11-5.96-.22-8.62-.29-3.09-.08-5.51-.1-5.93.01-.3.08-.49.31-.58.63-.17.57-.14,3.16-.11,3.47.06,0,.12,0,.19,0,.12,0,.41,0,.74,0,.03,0,.05,0,.08,0,.04,0,.07,0,.11,0ZM20.02,13.12c.02-.13.05-.25.09-.36.19-.58.61-1,1.28-1.02.06,0,.11,0,.17-.01.05,0,.17,0,.33,0,.48,0,1.36.03,1.99.15.39.08.68.43.7.86.08,1.44-.02,3.76-2.28,3.69-.24,0-.5-.03-.78-.1-.93-.2-1.52-1.47-1.54-2.62,0-.2,0-.4.04-.59Z" fill="#1a1a1a"/>
      <path d="M15.99,12.94s0-.02,0-.03c.02-.25,0-1.38-1.93-1.38-.14,0-.29,0-.45.02l-.36.03c-.42.04-.79.14-.99.3-.03.02-.06.05-.09.08-.01.01-.02.03-.04.04-.02.03-.05.06-.07.09,0,.01-.01.02-.02.04-.02.03-.04.07-.06.1,0,0,0,0,0,.01-.22.47-.21,1.16-.16,1.68,0,.02,0,.05,0,.07,0,.02,0,.03,0,.05.02.14.03.26.05.36,0,0,0,.02,0,.03,0,.02,0,.05.01.07.01.08.02.13.02.13,0,0,.05,0,.13,0,.25,0,.83-.04,1.21-.1,0,0,.01,0,.02,0,0,0,.01,0,.02,0-.18-.19-.3-.47-.3-.78,0-.58.4-1.04.89-1.04s.89.47.89,1.04c0,.07,0,.13-.01.2,0,0,0,0,.01,0,.31-.21.63-.47.84-.65.08-.07.15-.13.2-.17.06-.05.19-.15.19-.15Z" fill="#fff"/>
      <path d="M13.67,14.43s.03,0,.04,0c0,0,0,0,0,0-.01,0-.03,0-.05.01Z" fill="#fff"/>
      <path d="M14.14,14.29c-.12.05-.25.09-.39.13,0,0,.02,0,.03,0,.34-.08.5-.17.75-.34,0,0,.02-.01.02-.02-.16.1-.3.19-.42.23Z" fill="#fff"/>
      <path d="M21.53,16.32c.28.06.55.09.78.1,2.26.07,2.36-2.25,2.28-3.69-.02-.43-.31-.79-.7-.86-.63-.12-1.51-.15-1.99-.15-.16,0-.28,0-.33,0-.06,0-.11,0-.17.01-.68.03-1.09.45-1.28,1.02-.04.12-.07.24-.09.36-.03.19-.05.39-.04.59.02,1.15.61,2.41,1.54,2.62ZM22.29,13.03c.5,0,.91.47.91,1.04s-.41,1.04-.91,1.04-.91-.47-.91-1.04.41-1.04.91-1.04Z" fill="#fff"/>
      <ellipse cx="22.29" cy="14.07" rx=".91" ry="1.04" fill="#1a1a1a"/>
      <path d="M4.49,17.36c-.57,0-1.03.26-1.03.57s.46.57,1.03.57,1.03-.26,1.03-.57-.46-.57-1.03-.57Z" fill="#1a1a1a"/>
      <ellipse cx="7.5" cy="19.59" rx="1.03" ry=".57" fill="#1a1a1a"/>
      <path d="M13.29,14.51c.13-.02.26-.05.38-.07.02,0,.03,0,.05-.01,0,0,.02,0,.03,0,0,0,0,0,0,0,.14-.04.27-.08.39-.13.12-.05.26-.13.42-.23.06-.04.12-.08.19-.13,0,0,0,0,0,0,.01-.06.01-.13.01-.2,0-.58-.4-1.04-.89-1.04s-.89.47-.89,1.04c0,.31.12.59.3.78,0,0,0,0,0,0,0,0,0,0,0,0Z" fill="#1a1a1a"/>
    </g>
  </g>
</svg> Germany**

Learn more at [rhesis.ai](https://rhesis.ai)
