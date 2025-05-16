# Getting Started

This guide will help you set up and run the Rhesis frontend application locally for development.

## Prerequisites

Before you begin, ensure you have the following installed:

* [Node.js](https://nodejs.org/) >=18.x.x
* [npm](https://www.npmjs.com/) or [Yarn](https://yarnpkg.com/)
* Git

## Installation Steps

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

## Development Workflow

### Available Scripts

* `npm run dev`: Starts the development server with Turbo.
* `npm run build`: Builds the application for production (runs type-check and lint first).
* `npm run start`: Starts a production server (after building).
* `npm run lint`: Lints the codebase using Next.js's built-in ESLint configuration.
* `npm run type-check`: Validates TypeScript types.
* `npm run clean`: Removes the .next directory.

### Code Editor Setup

We recommend using Visual Studio Code with the following extensions:

* ESLint
* Prettier
* TypeScript and JavaScript Language Features
* Material Icon Theme (optional)
* GitLens (optional)

### Recommended VSCode Settings

Create or update your `.vscode/settings.json` file with:

```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  "typescript.tsdk": "node_modules/typescript/lib",
  "typescript.enablePromptUseWorkspaceTsdk": true
}
```

## Next Steps

After setting up your development environment:

1. Explore the [Architecture Overview](./architecture.md) to understand the project structure
2. Check out the [Component Library](./components.md) to learn about available UI components
3. Review the [API Integration](./api-integration.md) documentation to understand backend connectivity
4. Read the [Contributing Guidelines](./contributing.md) before making changes

## Troubleshooting

### Common Issues

#### "Module not found" errors
- Ensure all dependencies are installed
- Check for typos in import paths
- Verify that the module exists in `node_modules`

#### Authentication Issues
- Verify environment variables are correctly set
- Check browser console for errors
- Ensure the backend API is running and accessible

#### Build Errors
- Run `npm run clean` to clear the build cache
- Verify TypeScript types with `npm run type-check`
- Check for ESLint errors with `npm run lint`

For additional help, please refer to the [Next.js documentation](https://nextjs.org/docs) or reach out to the team on Discord. 