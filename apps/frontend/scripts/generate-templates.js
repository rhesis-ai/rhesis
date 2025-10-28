#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

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

  const iconMap = iconImports.map(icon => `  ${icon},`).join('\n');

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
import { TestTemplate } from '@/app/(protected)/tests/new-generated/components/shared/types';

// Icon mapping for YAML references
const iconMap: Record<string, React.ComponentType<any>> = {
${iconMap}
};

// Generated templates from YAML
export const TEMPLATES: TestTemplate[] = [
${templatesCode}
];
`;
};

// Generate and write the file
try {
  const generatedContent = generateTypeScriptFile(config.templates);
  const outputPath = path.join(
    __dirname,
    '../src/config/test-templates.generated.ts'
  );

  fs.writeFileSync(outputPath, generatedContent, 'utf8');
  console.log('Successfully generated test-templates.generated.ts');
  console.log(`Generated ${config.templates.length} templates`);
} catch (error) {
  console.error('Error generating templates:', error);
  process.exit(1);
}
