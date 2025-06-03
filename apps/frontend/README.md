# Rhesis Frontend

<p align="center">
  <a href="https://github.com/rhesis-ai/rhesis/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/rhesis-ai/rhesis" alt="License">
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

> The intuitive frontend for Rhesis, enabling teams to create, manage, and analyze test cases for Gen AI applications.

## Overview

The Rhesis frontend provides a modern, responsive user interface for the Rhesis platform. It allows users to:

- Create and manage comprehensive test suites for Gen AI applications
- Visualize test results and identify patterns
- Collaborate with team members on test case development
- Track performance improvements over time
- Ensure AI systems meet regulatory and ethical standards

## Tech Stack

* **Framework:** [Next.js](https://nextjs.org/) 15.3.0 with App Router
* **Language:** [TypeScript](https://www.typescriptlang.org/) 5.8.3
* **UI:** [Material UI (MUI)](https://mui.com/) v6
* **Authentication:** [NextAuth.js](https://next-auth.js.org/) 5.0.0-beta.25
* **State Management:** React Context API
* **Styling:** MUI theming with Emotion
* **Data Visualization:** [Recharts](https://recharts.org/) 2.15.0
* **Data Grid:** MUI X Data Grid
* **Flow Visualization:** [React Flow](https://reactflow.dev/) 11.11.4
* **Code Editor:** [Monaco Editor](https://microsoft.github.io/monaco-editor/)
* **Icons:** MUI Icons, Lucide React
* **Date Handling:** date-fns, dayjs
* **React:** React 19

## Project Structure

A brief overview of the key directories:

* `src/app/`: Next.js App Router with route groups and protected routes
  * `(protected)/`: Authentication-protected routes (dashboard, projects, tests, etc.)
  * `api/`: API routes
  * `auth/`: Authentication pages
* `src/components/`: Shared UI components
  * `common/`: Reusable components (charts, tables, data grids)
  * `layout/`: Layout components
  * `navigation/`: Navigation components
  * `providers/`: Context providers
  * `auth/`: Authentication components
* `src/utils/`: Utility functions and services
  * `api-client/`: API client implementation with typed interfaces
* `src/actions/`: Server actions
* `src/types/`: TypeScript type definitions
* `src/styles/`: Theme configuration
* `src/constants/`: Application constants
* `public/`: Static assets

## Prerequisites

* [Node.js](https://nodejs.org/) >=18.x.x
* [npm](https://www.npmjs.com/) or [Yarn](https://yarnpkg.com/)

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/rhesis-ai/rhesis.git
cd rhesis/apps/frontend
```

### 2. Install Dependencies

```bash
npm install
# or
yarn install
```

### 3. Set Up Environment Variables

Copy the example environment file and fill in the required values:

```bash
cp .env.example .env.local
```

Update `.env.local` with the necessary configurations:

* `NEXTAUTH_SECRET`: Generate one using `npx auth secret` or `openssl rand -hex 32`.
* `NEXT_PUBLIC_API_BASE_URL`: The base URL for your backend API.
* `GOOGLE_CLIENT_ID`: Your Google OAuth Client ID.
* `GOOGLE_CLIENT_SECRET`: Your Google OAuth Client Secret.
* `AUTH_SECRET`: Should be the same as `NEXTAUTH_SECRET`.

### 4. Run the Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser to see the application.

## Available Scripts

In the `apps/frontend` directory, you can run several commands:

* `npm run dev`: Starts the development server with Turbo.
* `npm run build`: Builds the application for production (runs type-check and lint first).
* `npm run start`: Starts a production server (after building).
* `npm run lint`: Lints the codebase using Next.js's built-in ESLint configuration.
* `npm run type-check`: Validates TypeScript types.
* `npm run clean`: Removes the .next directory.

## Deployment

This Next.js application can be easily deployed using the included Dockerfile or on platforms like [Vercel](https://vercel.com/) or [Netlify](https://www.netlify.com/).

Refer to the [Next.js deployment documentation](https://nextjs.org/docs/deployment) for more details.

## Contributing

We welcome contributions to the Rhesis frontend! Rhesis thrives thanks to our amazing community of contributors.

### Ways to Contribute

- **Code**: Fix bugs, implement features, or improve documentation
- **UI/UX**: Improve the user interface and experience
- **Testing**: Write unit or integration tests
- **Feedback**: Report bugs, suggest features, or share your experience using Rhesis

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write or update tests
5. Submit a pull request

For detailed guidelines, please see [CONTRIBUTING.md](../../CONTRIBUTING.md).

## License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.

## Support

For questions, issues, or feature requests:
- Visit our [documentation](https://docs.rhesis.ai)
- Join our [Discord server](https://discord.rhesis.ai)
- Contact us at hello@rhesis.ai
- Create an issue in the [GitHub repository](https://github.com/rhesis-ai/rhesis/issues)

---

Made in Potsdam, Germany 🇩🇪

Visit [rhesis.ai](https://rhesis.ai) to learn more.
