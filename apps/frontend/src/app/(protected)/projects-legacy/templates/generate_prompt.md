You are generating a prompt that will be used to create test prompts for evaluating an LLM application. Your task is to construct a precise and structured prompt that incorporates a given requirement, scenario, and persona to guide test case generation.

### **Inputs:**
- **Requirement:** {requirement}
- **Scenario:** {scenario}
- **Persona:** {persona}

### **Instructions:**
1. Formulate a structured prompt that instructs an LLM to generate a user query.
2. Ensure that the generated prompt reflects the requirement, scenario, and persona without directly producing a test case.
3. The prompt should describe:
   - The type of user input expected.
   - The emotional tone and communication style based on the persona.
   - Any specific challenges introduced by the scenario.
4. Use clear and directive language to guide LLM-generated test prompts.
5. Return the prompt as a string, and nothing else. Do not use any other formatting or comments.

### **Example Output:**
(For **Requirement:** *Claims Processing Time*, **Scenario:** *New Claim Submission*, **Persona:** *New Policyholder*:)
Create a user prompt where the person is a first-time insurance customer, feeling slightly anxious and needing reassurance. The tone should be polite and seeking guidance, reflecting their unfamiliarity with the process.