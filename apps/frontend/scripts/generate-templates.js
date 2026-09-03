#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');
const prettier = require('prettier');

// Read the YAML file
const yamlPath = path.join(__dirname, '../src/config/test-templates.yml');
const fileContents = fs.readFileSync(yamlPath, 'utf8');
const config = yaml.load(fileContents);

// Icon mapping for the generated file
const iconImports = [
  'BalanceIcon',
  'LanguageIcon',
  'VerifiedUserIcon',
  'PrivacyTipIcon',
  'RecordVoiceOverIcon',
  'PublicIcon',
  'MenuBookIcon',
  'FavoriteIcon',
  'LightbulbIcon',
  'TroubleshootIcon',
  'AccountBalanceIcon',
  'CampaignIcon',
];

// Generate the TypeScript file content
const generateTypeScriptFile = templates => {
  const imports = iconImports
    .map(
      icon =>
        `import ${icon} from '@mui/icons-material/${icon.replace('Icon', '')}';`
    )
    .join('\n');

  const templatesCode = templates
    .map(template => {
      const topics = JSON.stringify(template.topics);
      const category = JSON.stringify(template.category);

      return `  {
    id: '${template.id}',
    name: '${template.name}',
    description: '${template.description}',
    icon: ${template.icon},
    color: '${template.color}',
    prompt: '${template.prompt}',
    topics: ${topics},
    category: ${category},
    popularity: '${template.popularity}',
  }`;
    })
    .join(',\n');

  return `// This file is auto-generated from test-templates.yml
// Do not edit manually - run 'npm run generate-templates' to regenerate

${imports}
import { TestTemplate } from '@/app/(protected)/test-sets/new-generated/components/shared/types';

// Generated templates from YAML
export const TEMPLATES: TestTemplate[] = [
${templatesCode}
];
`;
};

// Generate and write the file.
// The output is checked in, so it has to be formatted the way Prettier would
// leave it. Writing it raw makes `prettier --check` fail and shows every
// `prebuild` run as a large content-identical diff in git.
async function main() {
  const generatedContent = generateTypeScriptFile(config.templates);
  const outputPath = path.join(
    __dirname,
    '../src/config/test-templates.generated.ts'
  );

  const prettierConfig = await prettier.resolveConfig(outputPath);
  const formatted = await prettier.format(generatedContent, {
    ...prettierConfig,
    filepath: outputPath,
  });

  fs.writeFileSync(outputPath, formatted, 'utf8');
  console.log('Successfully generated test-templates.generated.ts');
  console.log(`Generated ${config.templates.length} templates`);
}

main().catch(error => {
  console.error('Error generating templates:', error);
  process.exit(1);
});
