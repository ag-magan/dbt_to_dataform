import re
import json
from anthropic import Anthropic
import time
from pathlib import Path
import os
import httpx
from dbt_to_dataform.conversion_report import ConversionReport

class SyntaxChecker:
    def __init__(self, anthropic_api_key: str):
        self.anthropic_api_key = anthropic_api_key
        # Set the API key as an environment variable as a fallback
        os.environ["ANTHROPIC_API_KEY"] = anthropic_api_key
        # Create a custom httpx client without proxies
        self.http_client = httpx.Client(timeout=None, follow_redirects=True)
        # Initialize the client with a custom httpx client
        self.anthropic_client = Anthropic(api_key=anthropic_api_key, http_client=self.http_client)
        self.model = "claude-3-7-sonnet-latest"
        
    def check_and_correct_syntax(self, file_path: Path, content: str, conversion_report: ConversionReport) -> tuple:
        print(f"Checking syntax for file: {file_path}")
        
        if not self.anthropic_api_key:
            print("Anthropic API key not provided. Skipping syntax check.")
            return content, None

        if not isinstance(content, str):
            print(f"Warning: content is not a string. Type: {type(content)}")
            return str(content) if content is not None else "", None

        file_type = self._get_file_type(file_path)
        system_prompt = self._get_system_prompt(file_type)
        user_prompt = self._get_user_prompt(file_type, content)

        try:
            print(f"Sending to Claude API for syntax checking...")
            
            response = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=64000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2
            )
            
            result = response.content[0].text.strip()
            print(f"Claude API response received for {file_path}")

            if result.lower() != "valid":
                conversion_report.add_issue(
                    str(file_path),
                    "Syntax Correction",
                    f"The following changes were made: {result}"
                )
                print(f"Syntax corrections made for {file_path}")
                corrected_code = self._extract_corrected_code(result, file_type)
                return corrected_code if corrected_code else content, result
            else:
                print(f"No syntax corrections needed for {file_path}")
            
            return content, None

        except Exception as e:
            print(f"Claude API error during syntax check for {file_path}: {str(e)}")
            # Attempt to retry once
            try:
                print("Retrying syntax check after 2 seconds...")
                time.sleep(2)
                
                response = self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=64000,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.2
                )
                
                result = response.content[0].text.strip()
                if result.lower() != "valid":
                    corrected_code = self._extract_corrected_code(result, file_type)
                    return corrected_code if corrected_code else content, result
            except Exception as retry_error:
                print(f"Retry also failed: {str(retry_error)}")
                
            return content, None
        except Exception as e:
            print(f"Unexpected error during syntax check for {file_path}: {str(e)}")
            return content, None

    def _get_file_type(self, file_path: Path) -> str:
        if file_path.suffix == '.sqlx':
            return 'sqlx'
        elif file_path.name == 'dataform.json':
            return 'json'
        else:
            return 'unknown'

    def _get_system_prompt(self, file_type: str) -> str:
        if file_type == 'sqlx':
            return """
            You are an expert in Dataform SQLX syntax and BigQuery SQL. Your task is to check and correct Dataform SQLX code.
            
            Dataform SQLX files are SQL files with JavaScript configuration blocks at the top. These files typically:
            1. Start with a JavaScript config block enclosed in curly braces.
            2. Have SQL code for the query after the config block.
            3. May contain JavaScript template literals using ${} syntax for variable interpolation.
            4. May reference other tables using ${ref("table_name")} syntax.
            5. May reference JavaScript functions from included files.
            
            Common issues to look for:
            1. Missing or malformed config blocks
            2. Incorrect JavaScript syntax inside config blocks
            3. Improperly closed template literals or missing backticks
            4. Invalid BigQuery SQL syntax
            5. Malformed ref() or source() references
            
            When reporting corrections, be specific about:
            1. What was wrong
            2. How you fixed it
            3. Why the correction is needed
            
            If the code is valid, just respond with "Valid".
            """
        elif file_type == 'json':
            return """
            You are an expert in Dataform configuration and JSON syntax. Your task is to check and correct Dataform JSON configuration files.
            
            Dataform's dataform.json file contains project configuration including:
            1. Project name and default schema
            2. Warehouse type (usually "bigquery")
            3. Project variables
            4. Default database/dataset configurations
            
            Common issues to look for:
            1. Invalid JSON syntax (missing commas, brackets, etc.)
            2. Missing required fields
            3. Invalid values for configuration options
            4. Improper nesting of configuration objects
            
            When reporting corrections, be specific about:
            1. What was wrong
            2. How you fixed it
            3. Why the correction is needed
            
            If the JSON is valid, just respond with "Valid".
            """
        else:
            return """
            You are an expert code reviewer. Your task is to check the provided code for syntax errors and other issues.
            
            If the code appears valid, just respond with "Valid".
            If you find issues, explain what's wrong and provide corrected code.
            """

    def _get_user_prompt(self, file_type: str, content: str) -> str:
        if file_type == 'sqlx':
            return f"""
            Check if the following Dataform SQLX code is valid. If it's not valid, correct it and explain the changes made.
            If it's valid, just respond with "Valid".

            Always include the full corrected code in your response, even if only small changes were made.
            Wrap the corrected code in ```sqlx and ``` tags.

            Code:
            {content}
            """
        elif file_type == 'json':
            return f"""
            Check if the following dataform.json configuration is valid. If it's not valid, correct it and explain the changes made.
            If it's valid, just respond with "Valid".

            Always include the full corrected JSON in your response, even if only small changes were made.
            Wrap the corrected JSON in ```json and ``` tags.

            JSON:
            {content}
            """
        else:
            return f"Unknown file type. Please check the content:\n\n{content}"

    def _extract_corrected_code(self, result: str, file_type: str) -> str:
        if file_type == 'sqlx':
            sqlx_code_blocks = re.findall(r'```sqlx(.*?)```', result, re.DOTALL)
            if sqlx_code_blocks:
                return sqlx_code_blocks[-1].strip()
            
            # Fallback to general code blocks
            code_blocks = re.findall(r'```(.*?)```', result, re.DOTALL)
            if code_blocks:
                return code_blocks[-1].strip()
                
        elif file_type == 'json':
            json_code_blocks = re.findall(r'```json(.*?)```', result, re.DOTALL)
            if json_code_blocks:
                try:
                    # Attempt to parse the JSON to ensure it's valid
                    json_content = json_code_blocks[-1].strip()
                    json.loads(json_content)  # Just to validate
                    return json_content
                except json.JSONDecodeError:
                    print("Warning: Extracted JSON is not valid.")
                    
            # Fallback to general code blocks
            code_blocks = re.findall(r'```(.*?)```', result, re.DOTALL)
            if code_blocks:
                try:
                    json_content = code_blocks[-1].strip()
                    json.loads(json_content)  # Just to validate
                    return json_content
                except (json.JSONDecodeError, IndexError):
                    print("Warning: No valid JSON found in code blocks.")

        # More general extractions if the code blocks aren't found
        corrected_code_match = re.search(r'(?:Corrected|Fixed|Updated) (?:code|version):\s*(.*)', result, re.DOTALL | re.IGNORECASE)
        if corrected_code_match:
            return corrected_code_match.group(1).strip()

        # Last resort: look for code-like patterns
        lines = result.split('\n')
        if file_type == 'sqlx':
            for i, line in enumerate(lines):
                if line.strip().endswith('{') or line.strip().startswith('config') or 'SELECT' in line.upper():
                    return '\n'.join(lines[i:]).strip()
        elif file_type == 'json':
            for i, line in enumerate(lines):
                if line.strip().startswith('{'):
                    try:
                        potential_json = '\n'.join(lines[i:]).strip()
                        json.loads(potential_json)  # Just to validate
                        return potential_json
                    except json.JSONDecodeError:
                        continue

        # If we couldn't extract anything meaningful, return empty string
        print("Warning: Could not extract corrected code from Claude's response.")
        return ""