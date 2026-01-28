"""
Prompt extraction strategies for Garak probes.

This module contains methods to extract prompts from Garak probe classes
using multiple strategies (class attributes, instantiation, source parsing).
"""

import ast
import inspect
import re
import textwrap
from typing import Any, Dict, List

from .models import GENERATOR_PLACEHOLDER


class PromptExtractor:
    """
    Extracts prompts from Garak probe classes.

    Garak probes may set self.prompts in different ways:
    1. As a class attribute
    2. In __init__() (e.g., encoding probes)
    3. In the probe() method (e.g., DAN probes with f-strings)
    4. Dynamically in probe() with loops (e.g., Ablation probes)

    This class tries multiple strategies to extract prompts.
    """

    def extract_prompts(self, probe_class: type) -> List[str]:
        """
        Extract prompts from a probe class using multiple strategies.

        Args:
            probe_class: The probe class to extract prompts from

        Returns:
            List of prompt strings with generator.name replaced by placeholder
        """
        prompts = []

        try:
            # First try: check if class already has prompts attribute
            if hasattr(probe_class, "prompts"):
                class_prompts = probe_class.prompts
                if isinstance(class_prompts, (list, tuple)) and class_prompts:
                    return list(class_prompts)

            # Second try: instantiate the probe to get prompts set in __init__
            try:
                instance = probe_class()
                if hasattr(instance, "prompts") and instance.prompts:
                    return list(instance.prompts)
            except Exception:
                pass  # Fall through to other extraction methods

            # Third try: execute the prompt-generation portion of probe() with a mock
            prompts = self._extract_by_execution(probe_class)
            if prompts:
                return prompts

            # Fourth try: parse source code to extract list literal
            prompts = self._extract_from_source(probe_class)

        except Exception:
            pass  # Extraction failed - return empty list

        return prompts

    def _extract_by_execution(self, probe_class: type) -> List[str]:
        """
        Try to extract prompts by executing the prompt-generation code.

        Creates a mock generator and runs the probe's prompt generation logic.
        This handles dynamic patterns like loops and conditionals.

        Args:
            probe_class: The probe class to extract prompts from

        Returns:
            List of prompt strings, or empty list if extraction fails
        """
        if not hasattr(probe_class, "probe"):
            return []

        try:
            source = inspect.getsource(probe_class.probe)
        except (OSError, TypeError):
            return []

        # Check if this is a dynamic prompt generation pattern
        # (uses loops or conditionals to build prompts)
        has_loop = "for " in source and "self.prompts" in source
        has_append = ".append(" in source and "self.prompts" in source

        if not (has_loop or has_append):
            return []

        # Try to execute the prompt generation code with a mock
        try:
            # Create mock generator
            class MockGenerator:
                name = GENERATOR_PLACEHOLDER

            generator = MockGenerator()

            # Create an instance without calling probe()
            instance = probe_class.__new__(probe_class)
            instance.prompts = []

            # Extract the prompt-generation portion of the probe() method
            # Dedent the entire source first
            dedented_source = textwrap.dedent(source)
            code_lines = dedented_source.split("\n")
            prompt_code_lines = []
            in_prompt_section = False
            base_indent = None

            for line in code_lines:
                stripped = line.strip()

                # Skip empty lines and the def line
                if not stripped:
                    if in_prompt_section and prompt_code_lines:
                        prompt_code_lines.append("")
                    continue

                if stripped.startswith("def probe"):
                    in_prompt_section = True
                    continue

                if not in_prompt_section:
                    continue

                # Stop at return statement or generator calls
                if stripped.startswith("return ") or "generator.generate" in line:
                    break

                # Capture everything in the method body until we hit the stopping point
                # Find the base indentation level from the first real line
                if base_indent is None and line and not line.isspace():
                    base_indent = len(line) - len(line.lstrip())

                prompt_code_lines.append(line)

            if not prompt_code_lines:
                return []

            # Build executable code - dedent to remove method body indentation
            prompt_code = "\n".join(prompt_code_lines)
            prompt_code = textwrap.dedent(prompt_code)

            # Create execution context with common builtins
            exec_globals = {
                "generator": generator,
                "self": instance,
                "range": range,
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "list": list,
                "dict": dict,
                "set": set,
                "tuple": tuple,
                "enumerate": enumerate,
                "zip": zip,
                "min": min,
                "max": max,
                "sum": sum,
                "abs": abs,
                "True": True,
                "False": False,
                "None": None,
            }

            exec(prompt_code, exec_globals)

            # Get the generated prompts
            if hasattr(instance, "prompts") and instance.prompts:
                return [str(p) for p in instance.prompts]

        except Exception:
            pass  # Execution-based extraction failed - fall through to return empty

        return []

    def _extract_from_source(self, probe_class: type) -> List[str]:
        """
        Extract prompts by parsing source code for list literals.

        This handles simpler cases where prompts are assigned as a list literal.

        Args:
            probe_class: The probe class to extract prompts from

        Returns:
            List of prompt strings, or empty list if extraction fails
        """
        prompts = []

        if not hasattr(probe_class, "probe"):
            return prompts

        try:
            source = inspect.getsource(probe_class.probe)
        except (OSError, TypeError):
            return prompts

        # Pattern matches: self.prompts = [ ... ] (non-empty list)
        pattern = r"self\.prompts\s*=\s*\["
        match = re.search(pattern, source)
        if not match:
            return prompts

        # Find the matching closing bracket
        start_idx = match.end() - 1  # Position of opening [
        bracket_count = 0
        prompts_str = ""

        # Track whether we're inside a string to handle brackets in strings
        in_string = False
        string_char = None
        escape_next = False

        for i, char in enumerate(source[start_idx:]):
            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            # Handle string boundaries
            if char in ('"', "'"):
                # Check for triple quotes
                remaining = source[start_idx + i :]
                if remaining.startswith('"""') or remaining.startswith("'''"):
                    triple_quote = remaining[:3]
                    if not in_string:
                        in_string = True
                        string_char = triple_quote
                    elif string_char == triple_quote:
                        in_string = False
                        string_char = None
                elif not in_string:
                    in_string = True
                    string_char = char
                elif string_char == char:
                    in_string = False
                    string_char = None

            # Only count brackets outside strings
            if not in_string:
                if char == "[":
                    bracket_count += 1
                elif char == "]":
                    bracket_count -= 1
                    if bracket_count == 0:
                        prompts_str = source[start_idx : start_idx + i + 1]
                        break

        if not prompts_str or prompts_str == "[]":
            return prompts

        # Create a mock generator class for evaluating f-strings
        class MockGenerator:
            name = GENERATOR_PLACEHOLDER

        generator = MockGenerator()

        # Try to evaluate the prompts list
        try:
            local_vars: Dict[str, Any] = {"generator": generator}
            exec(f"result = {prompts_str}", {"generator": generator}, local_vars)
            result = local_vars.get("result", [])
            if isinstance(result, (list, tuple)):
                prompts = [str(p) for p in result]
        except Exception:
            # If eval fails, try to count list items using AST
            try:
                tree = ast.parse(prompts_str, mode="eval")
                if isinstance(tree.body, ast.List):
                    count = len(tree.body.elts)
                    class_name = probe_class.__name__
                    prompts = [f"[Prompt {i + 1} from {class_name}]" for i in range(count)]
            except Exception:
                pass

        return prompts
