# LLM-Assisted Smart Code Extraction

## Overview

The Virtual Lab platform offers two modes of code extraction from meeting transcripts:

1. **Regex-based extraction** (`/api/artifacts/meeting/{id}/extract`) - Fast, rule-based
2. **LLM-assisted smart extraction** (`/api/artifacts/meeting/{id}/extract-smart`) - Intelligent, context-aware

This document focuses on the **smart extraction** feature.

## Key Features

### 1. Context-Aware Code Extraction

The LLM analyzes the entire meeting conversation to:
- Extract code snippets **even without standard markdown formatting**
- Understand the purpose and context of each code block
- Identify related code that should be grouped together

**Example:**
```
Agent: "The main function should be: def process_data(df): return df.dropna()"
```
Smart extraction will recognize this as code even without ``` markers.

### 2. Intelligent Project Structure Inference

Based on the discussion content, the LLM infers:
- **Project type** (web_app, data_science, ml_pipeline, cli_tool, library, etc.)
- **Folder structure** (src/, tests/, models/, config/, etc.)
- **Entry point** (main.py, app.py, etc.)
- **Project documentation** (auto-generated README.md)

**Example output:**
```json
{
  "project_type": "web_app",
  "suggested_folders": ["app", "models", "templates", "tests"],
  "entry_point": "app/main.py",
  "readme_content": "# Flask Web Application\n\nA web app with user authentication..."
}
```

### 3. Meaningful File Naming and Organization

Instead of generic names like `code_1.py`, the LLM generates:
- **Semantic filenames** based on code purpose
- **Proper folder paths** (e.g., `src/models/pipeline.py`, not just `pipeline.py`)
- **Related file grouping** (merging related snippets into cohesive files)

**Example:**
- Before (regex): `data_processor.py`, `load_data.py`, `clean_data.py`
- After (LLM): `src/data/pipeline.py` (all data processing code combined)

### 4. Automatic Dependency Analysis

The LLM:
- Identifies **all required packages** from imports
- Maps import names to **PyPI package names** (e.g., `sklearn` → `scikit-learn`)
- Generates accurate **requirements.txt**
- Detects **version constraints** mentioned in comments

**Example:**
```python
# Code mentions: "Using pandas 2.0+ for better performance"
# Generated requirements.txt:
pandas>=2.0.0
numpy
scikit-learn
```

### 5. Code Description Generation

Each extracted file includes:
- **Human-readable description** of what the code does
- **Source agent attribution** (who wrote it)
- **Related files** (dependencies and relationships)

## API Usage

### Endpoint

```
POST /api/artifacts/meeting/{meeting_id}/extract-smart
```

### Request Body (Optional)

```json
{
  "model": "gpt-4"  // Optional: specify LLM model (default: gpt-4)
}
```

### Response

```json
{
  "project_type": "data_science",
  "suggested_folders": ["data", "notebooks", "src", "models", "tests"],
  "entry_point": "src/train.py",
  "readme_content": "# Machine Learning Pipeline\n\n...",
  "files": [
    {
      "filename": "src/data/loader.py",
      "language": "python",
      "content": "import pandas as pd\n\ndef load_dataset(path):\n    return pd.read_csv(path)",
      "description": "Data loading utilities for CSV files",
      "dependencies": ["pandas"],
      "source_agent": "Data Engineer",
      "related_files": ["src/train.py"]
    },
    {
      "filename": "src/train.py",
      "language": "python",
      "content": "from sklearn.ensemble import RandomForestClassifier\n...",
      "description": "Main training script for the ML model",
      "dependencies": ["scikit-learn"],
      "source_agent": "ML Researcher",
      "related_files": ["src/data/loader.py", "models/trained_model.pkl"]
    }
  ],
  "requirements_txt": "pandas>=1.5.0\nscikit-learn\nnumpy"
}
```

### Database Storage

Smart extraction automatically creates artifacts in the database:
- **Code files** (from the `files` array)
- **README.md** (auto-generated documentation)
- **requirements.txt** (Python dependencies)

## Comparison: Regex vs. LLM-Assisted

| Feature | Regex Extraction | LLM-Assisted Smart Extraction |
|---------|-----------------|------------------------------|
| **Speed** | ⚡ Fast (~100ms) | 🐢 Slower (~5-10s) |
| **Code Format** | Requires markdown blocks | Extracts any format |
| **File Naming** | Generic (class/function names) | Semantic (purpose-based) |
| **Folder Structure** | Flat or simple hints | Inferred project structure |
| **Code Grouping** | One block = one file | Related code combined |
| **Dependencies** | Basic import parsing | Smart PyPI mapping |
| **README Generation** | ❌ No | ✅ Yes |
| **Context Understanding** | ❌ No | ✅ Yes |
| **Cost** | Free | Requires API key + costs |

## When to Use Each Mode

### Use Regex Extraction (`/extract`) when:
- ✅ Meeting uses standard markdown code blocks
- ✅ Code is already well-organized
- ✅ You want instant results
- ✅ You want to minimize API costs

### Use Smart Extraction (`/extract-smart`) when:
- ✅ Code snippets lack proper formatting
- ✅ Multiple related code pieces need organization
- ✅ You want automatic project structure
- ✅ You need accurate dependency detection
- ✅ You want README and documentation
- ✅ Meeting discussion is complex with scattered code

## Example Use Case

### Meeting Transcript

```
User: "We need a Flask app with user authentication."

Backend Developer: "The main app should be: from flask import Flask; app = Flask(__name__)"

Frontend Developer: "And we need a login route."

Backend Developer: "Right, here's the auth logic:
class User:
    def __init__(self, username, password_hash):
        self.username = username
        self.password_hash = password_hash
"

Database Engineer: "Don't forget the database connection: from flask_sqlalchemy import SQLAlchemy; db = SQLAlchemy(app)"
```

### Smart Extraction Result

```
app/
  __init__.py          # Flask app initialization
  models/
    user.py            # User model class
  config.py            # Database configuration
  routes/
    auth.py            # Authentication routes
tests/
  test_auth.py         # (if discussed)
README.md              # Auto-generated project overview
requirements.txt       # flask, flask-sqlalchemy
```

### Regex Extraction Result (for comparison)

```
code_1.py              # from flask import Flask...
user.py                # class User:...
code_2.py              # from flask_sqlalchemy...
```

## Implementation Details

### Core Components

1. **`LLMCodeExtractor`** (`backend/app/core/llm_code_extractor.py`)
   - Main extraction logic
   - Project structure analysis
   - Requirements generation

2. **Smart Extract API** (`backend/app/api/artifacts.py`)
   - `/extract-smart` endpoint
   - Database artifact creation
   - Error handling with fallback

3. **Schemas** (`backend/app/schemas/artifact.py`)
   - `SmartExtractRequest`
   - `SmartExtractResponse`
   - `SmartExtractedFileResponse`

### LLM Prompts

The system uses carefully crafted prompts for:

1. **Project Structure Analysis**
   - Detect project type from keywords
   - Suggest appropriate folder structure
   - Generate README content

2. **Code Extraction**
   - Find all code snippets
   - Organize into logical files
   - Merge related code
   - Infer file paths

3. **Dependency Analysis**
   - Parse all imports
   - Map to PyPI packages
   - Include version constraints
   - Exclude standard library

## Testing

All smart extraction features are tested in `backend/tests/test_llm_code_extractor.py` (15 tests):

- Project structure inference (web_app, data_science, etc.)
- Code extraction without markdown
- Related code grouping
- Requirements generation
- API endpoint integration
- Database artifact storage

## Future Enhancements

Potential improvements:

1. **Multi-language support** - Currently optimized for Python
2. **Docker configuration** - Auto-generate Dockerfile
3. **CI/CD configs** - Generate GitHub Actions workflows
4. **Test generation** - Create test stubs for extracted code
5. **Code refactoring** - Suggest improvements during extraction
6. **Incremental extraction** - Update existing artifacts instead of recreating

## Error Handling

If smart extraction fails (e.g., LLM API error), the system:
1. Returns a clear error message
2. Suggests using `/extract` as fallback
3. Logs the error for debugging
4. Does NOT create partial artifacts

## Configuration

Smart extraction respects user's LLM settings:
- Uses stored API keys from the database
- Supports OpenAI, Anthropic, and DeepSeek
- Model selection via request parameter
- Automatic provider detection

## Cost Considerations

Smart extraction consumes LLM tokens:
- **Analysis prompt**: ~500-1000 tokens
- **Extraction prompt**: ~1000-2000 tokens (depends on transcript length)
- **Requirements prompt**: ~200-500 tokens

**Estimated cost per extraction** (GPT-4):
- Small meeting (<10 messages): ~$0.01-0.02
- Medium meeting (10-50 messages): ~$0.05-0.10
- Large meeting (>50 messages): ~$0.10-0.30

**Tip:** Use regex extraction first, then smart extraction only when needed.

## Security

- API keys are encrypted at rest
- LLM prompts do NOT include sensitive data
- Extracted code is stored securely
- User owns all generated artifacts

## Conclusion

Smart code extraction transforms unstructured meeting discussions into well-organized, production-ready project structures. It's particularly valuable for:
- **Research teams** discussing complex algorithms
- **Brainstorming sessions** with scattered code ideas
- **Prototyping meetings** where code evolves iteratively
- **Cross-team collaboration** with different coding styles

For simple, well-formatted code, regex extraction remains fast and cost-effective.
