# dbt to Dataform Migration Tool

This tool partially automates the process of converting dbt (data build tool) projects to Dataform, focusing on BigQuery as the data warehouse. It not a turn-key tool that handles all aspects of the migration for you, but it will take care of the simple (and some more complex) tasks so that you can concentrate on the more complex parts.

It leverages Anthropic's Claude API for complex conversions and syntax checking; to make use of these features you will need an Anthropic API key.

# Features

- Converts dbt models to Dataform SQLX files, with limitations as detailed below
- Translates dbt source definitions to Dataform declarations
- Converts dbt macros to Dataform functions using Claude 3.7 Sonnet (requires Anthropic API key)
- Preserves project structure, adapting it to Dataform best practices
- Handles (with limitations) dbt-specific Jinja syntax and converts it to JavaScript
- Supports conversion of dbt variables to Dataform project config variables
- Automatically converts common dbt_utils functions to their BigQuery equivalents
- Uses Claude to check and correct Dataform syntax in converted files (requires Anthropic API key)
- Generates a detailed conversion report highlighting potential issues and syntax corrections

## How does it work?

The migration tool employs a combination of rule-based transformations for standard conversions and AI-powered processing for more complex scenarios. This hybrid approach enables the tool to handle both straightforward translations and nuanced, context-dependent conversions effectively.

While the process is largely automated, it is designed to complement rather than replace human expertise. The tool provides a solid foundation for migration, but user intervention may be necessary for project-specific optimizations and handling of unsupported features.

The migration process comprises seven steps:

1. **Project Analysis**: 
   - The RepositoryAnalyzer scans the dbt project structure.
   - It identifies models, tests, macros, and YAML files.

2. **Project Configuration Conversion**:
   - The ProjectConfigConverter translates dbt_project.yml to dataform.json.
   - It handles project-wide settings and variables.

3. **Source Conversion**:
   - The SourceConverter processes dbt source definitions.
   - It creates individual SQLX files for each source table in the Dataform project.

4. **Model Conversion**:
   - The ModelConverter translates each dbt SQL model to a Dataform SQLX file.
   - It handles reference conversions, variable replacements, and macro translations.

5. **Macro Conversion**:
   - The MacroConverter transforms dbt macros into Dataform JavaScript functions.
   - Macros are converted using the Anthropic Claude API, for manual review, correction and completion

6. **Syntax Checking and Correction**:
   - The SyntaxChecker uses the Anthropic Claude API to verify and correct Dataform syntax in converted files.
   - Claude's powerful language understanding capabilities enable it to handle complex macros effectively.

7. **Report Generation**:
   - The ConversionReport creates a detailed report of the conversion process.
   - It highlights potential issues, syntax corrections, and areas needing manual review.

## Automatically Converted dbt_utils Functions

The following dbt_utils functions are automatically converted to their BigQuery equivalents:

1. `{{ dbt_utils.type_string() }}` -> `STRING`
2. `{{ dbt_utils.type_int() }}` -> `INT64`
3. `{{ dbt_utils.type_numeric() }}` -> `NUMERIC`
4. `{{ dbt_utils.type_timestamp() }}` -> `TIMESTAMP`
5. `{{ dbt_utils.star(from=ref('model_name')) }}` -> `*`
6. `{{ dbt_utils.surrogate_key(['col1','col2']) }}` -> `TO_HEX(MD5(CONCAT(CAST(col1 AS STRING), CAST(col2 AS STRING))))`
7. `{{ dbt_utils.datediff(...) }}` -> `DATE_DIFF(...)`
8. `{{ dbt_utils.dateadd(...) }}` -> `DATE_ADD(...)`
9. `{{ dbt_utils.date_trunc(...) }}` -> `DATE_TRUNC(...)`
10. `{{ dbt_utils.date_part(...) }}` -> `EXTRACT(...)`

## Use of Anthropic Claude API

1. **dbt Jinja Macro Conversions**:
   - The `MacroConverter` class uses Claude 3.7 Sonnet to convert dbt Jinja macros to Dataform JavaScript functions.
   - It sends the dbt macro code to the API and receives a converted JavaScript function.
   - The system prompt includes detailed guidelines and examples for conversion, with specific instructions for:
     - Proper JavaScript error handling
     - Variable scope and closure handling
     - BigQuery-specific SQL function handling
     - Converting Jinja template logic to JavaScript
   - Claude's powerful language understanding capabilities enable it to handle complex macros effectively.

2. **Syntax Checking and Correction**:
   - The `SyntaxChecker` class uses Claude to verify and correct the syntax of converted Dataform files.
   - It sends the converted SQLX content to the API, which checks for Dataform-specific syntax issues and suggests corrections.
   - The system prompt includes detailed guidance on Dataform's SQLX structure and common issues to look for.
   - Claude's high performance on code tasks makes it particularly effective at catching and fixing subtle syntax issues.

# Setup

1. Clone the repository:
```
git clone https://github.com/yourusername/dbt-to-dataform.git
cd dbt-to-dataform
```

2. Create and activate a virtual environment (optional but recommended):
```
python -m venv venv
source venv/bin/activate  # On Windows use venv\Scripts\activate
```
3. Install the required packages:
```
pip install -r requirements.txt
```

## API Key Security

This tool uses the Anthropic Claude API for complex conversions. To securely use this feature:

1. Create a `.env` file by copying the provided example:
```
cp .env.example .env
```

2. Edit the `.env` file to add your actual Anthropic API key:
```
ANTHROPIC_API_KEY=your-actual-api-key
```

3. **IMPORTANT**: Never commit your `.env` file or expose your API key in public repositories. The `.gitignore` file is already configured to exclude `.env` files.

You can also provide the API key directly as a command-line argument:
```
python main.py <dbt_repo_path> <output_path> --anthropic-api-key your-api-key
```

# Usage

```bash
python main.py <dbt_repo_path> <output_path> --anthropic-api-key <your-api-key>
```
<dbt_repo_path>: Path to the local dbt repository
<output_path>: Path to output the Dataform project
--anthropic-api-key: Optional. Your Anthropic API key for complex conversions and syntax checking
--verbose: Optional. Enable verbose output

## Post-Conversion Steps

After running the converter:

- Review the conversion_report.json and conversion_summary.txt files
- Address any issues highlighted in the conversion report
- Review and test all converted models, especially those flagged in the report
- Implement any custom logic that couldn't be automatically converted
- Update any remaining dbt-specific syntax or functions that weren't automatically handled

# Limitations

- Complex dbt macros may require manual adjustment after conversion
- Custom dbt tests might need additional implementation in Dataform
- The tool assumes a BigQuery setup; adjustments may be needed for other warehouses
- Certain dbt-specific features might not have direct equivalents in Dataform
- While this converter handles many aspects of dbt projects, some features are not currently supported or require manual intervention:

1. **Seeds**: The converter does not automatically handle dbt seed files. These CSV files need to be manually imported into your data warehouse and declared in Dataform.

2. **dbt Semantic Layer**: Dataform does not have an equivalent to dbt's semantic layer. Metric definitions and semantic models will need to be reimplemented using Dataform's capabilities.

3. **Snapshots**: While the converter attempts to translate dbt snapshots, Dataform's approach to slowly changing dimensions (SCDs) differs from dbt's. Manual adjustment may be necessary.

4. **Custom Tests**: dbt's custom tests don't have a direct equivalent in Dataform. These will need to be reimplemented using Dataform's assertion capabilities.

5. **Packages**: dbt packages are not automatically converted. You'll need to find Dataform equivalents or reimplement the functionality.

6. **Documentation**: dbt's documentation generation is not directly translated. Dataform has its own documentation features that will need to be set up manually.

7. **Exposures**: Dataform doesn't have a direct equivalent to dbt's exposures. This information will need to be managed outside of Dataform.

8. **Advanced Hooks**: While basic pre- and post-hooks can be converted, advanced hook usage in dbt might require manual implementation in Dataform.

Always review the conversion report and test thoroughly after conversion to ensure all critical functionality is preserved.

# Credit
All credit to https://github.com/rittmananalytics/ra_dbt_to_dataform/tree/main

# Contributing
Contributions to improve the converter are welcome. Please submit pull requests with clear descriptions of the changes and their purposes.

# License
MIT License
