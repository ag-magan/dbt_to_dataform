# macro_converter.py

from pathlib import Path
from anthropic import Anthropic
import time
import os
import httpx

class MacroConverter:
    def __init__(self, anthropic_api_key):
        # Set the API key as an environment variable as a fallback
        os.environ["ANTHROPIC_API_KEY"] = anthropic_api_key
        # Create a custom httpx client without proxies
        http_client = httpx.Client(timeout=None, follow_redirects=True)
        # Initialize the client with a custom httpx client
        self.anthropic_client = Anthropic(api_key=anthropic_api_key, http_client=http_client)
        self.model = "claude-3-7-sonnet-latest"
        
        self.system_prompt = """
        You are an expert in dbt (data build tool) and Dataform, specializing in converting dbt macros to JavaScript functions for Dataform.
        Your task is to convert dbt macros written in Jinja/SQL to JavaScript for use in Dataform.
        
        Guidelines for conversion:
        1. Convert Python/Jinja syntax to JavaScript precisely and idiomatically.
        2. Replace dbt-specific functions with Dataform equivalents:
           - `ref()` in dbt becomes `ref()` in Dataform 
           - `source()` in dbt becomes `ref('source_...')` in Dataform
           - dbt's `{{ }}` becomes JavaScript template literals using `${}`
        3. For SQL generation, use JavaScript template literals with backticks.
        4. Implement proper error handling in JavaScript using try/catch blocks.
        5. Maintain variable scope and handle closures appropriately in JavaScript.
        6. For dbt macro parameters, convert them to JavaScript function parameters.
        7. Add helpful comments explaining complex translations.
        8. Ensure correct handling of BigQuery SQL functions.
        
        Examples of conversions:
        
        dbt macro:
        ```sql
        {% macro date_spine(datepart, start_date, end_date) %}
            WITH date_spine AS (
                SELECT CAST({{ start_date }} AS DATE) as date_day
                UNION ALL
                SELECT DATEADD({{ datepart }}, 1, date_day)
                FROM date_spine
                WHERE date_day < CAST({{ end_date }} AS DATE)
            )
            SELECT * FROM date_spine
        {% endmacro %}
        ```
        
        Dataform JavaScript function:
        ```javascript
        function date_spine(datepart, start_date, end_date) {
          return `
            WITH date_spine AS (
                SELECT CAST(${start_date} AS DATE) as date_day
                UNION ALL
                SELECT DATEADD(${datepart}, 1, date_day)
                FROM date_spine
                WHERE date_day < CAST(${end_date} AS DATE)
            )
            SELECT * FROM date_spine
          `;
        }
        ```
        
        dbt macro with conditional logic:
        ```sql
        {% macro generate_surrogate_key(field_list) %}
        {% if target.type == 'bigquery' %}
            TO_HEX(MD5(CONCAT(
                {% for field in field_list %}
                    CAST({{ field }} AS STRING)
                    {% if not loop.last %}, {% endif %}
                {% endfor %}
            )))
        {% else %}
            MD5(CONCAT(
                {% for field in field_list %}
                    CAST({{ field }} AS VARCHAR)
                    {% if not loop.last %}, {% endif %}
                {% endfor %}
            ))
        {% endif %}
        {% endmacro %}
        ```
        
        Dataform JavaScript function:
        ```javascript
        function generate_surrogate_key(field_list) {
            // Dataform is BigQuery-specific, so we use the BigQuery implementation
            try {
                // Build concatenation of fields as strings
                const fieldsConcat = field_list.map(field => `CAST(${field} AS STRING)`).join(', ');
                return `TO_HEX(MD5(CONCAT(${fieldsConcat})))`;
            } catch (error) {
                throw new Error(`Error in generate_surrogate_key: ${error.message}`);
            }
        }
        ```
        
        Do not include any introductory text or explanations in your response - provide only the converted JavaScript function.
        """

    def convert_macros(self, dbt_project_path, dataform_output_path):
        macros_dir = Path(dbt_project_path) / 'macros'
        dataform_includes_dir = Path(dataform_output_path) / 'includes'
        dataform_includes_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Scanning for macros in {macros_dir}...")
        if not macros_dir.exists():
            print(f"Warning: macros directory {macros_dir} not found. Skipping macro conversion.")
            return
        
        for macro_file in macros_dir.glob('*.sql'):
            try:
                print(f"Converting macro file: {macro_file.name}")
                with open(macro_file, 'r') as f:
                    macro_content = f.read()

                converted_js = self._convert_with_anthropic(macro_content)
                
                if not converted_js.strip():
                    print(f"Warning: Empty conversion result for {macro_file.name}. Skipping.")
                    continue

                output_file = dataform_includes_dir / f"{macro_file.stem}.js"
                with open(output_file, 'w') as f:
                    f.write(converted_js.strip())  # Remove any leading/trailing whitespace

                print(f"✓ Successfully converted {macro_file.name} to {output_file.name}")
            except Exception as e:
                print(f"Error converting macro {macro_file.name}: {str(e)}")

    def _convert_with_anthropic(self, macro_content, max_retries=3):
        user_prompt = f"""
        Please convert this dbt macro to a JavaScript function for Dataform:
        
        ```sql
        {macro_content}
        ```
        """
        
        retry_count = 0
        while retry_count < max_retries:
            try:
                response = self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=64000,
                    system=self.system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.2
                )
                return response.content[0].text.strip()
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    raise
                print(f"API error: {str(e)}. Retrying in 2 seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(2)

    def update_macro_references(self, dataform_output_path: Path):
        definitions_dir = Path(dataform_output_path) / 'definitions'
        if not definitions_dir.exists():
            print(f"Warning: definitions directory {definitions_dir} not found. Skipping macro reference updates.")
            return
            
        print("Updating macro references in JavaScript files...")
        try:
            # Look for both .js and .sqlx files
            for file_path in definitions_dir.rglob('*.js'):
                self._update_references_in_file(file_path)
                
            for file_path in definitions_dir.rglob('*.sqlx'):
                self._update_references_in_file(file_path)
                
        except Exception as e:
            print(f"Error updating macro references: {str(e)}")
            
    def _update_references_in_file(self, file_path):
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Update macro references from dbt to Dataform syntax
            # More comprehensive than the basic replacement
            updated_content = content
            
            # Replace dbt Jinja style macro calls with JavaScript
            updated_content = updated_content.replace('{{ ', '${')
            updated_content = updated_content.replace(' }}', '}')
            
            # Update macro calls within backticks
            # This is more complex and might need further refinement

            if updated_content != content:
                with open(file_path, 'w') as f:
                    f.write(updated_content)
                print(f"Updated macro references in {file_path.name}")
                
        except Exception as e:
            print(f"Error updating references in {file_path.name}: {str(e)}")