# PPT Agent - AI-Powered Presentation Designer

The PPT Agent is an intelligent AI-powered presentation designer that creates professional presentations with AI-generated images. It automatically detects your needs and adapts its workflow based on what you provide - from just an idea to complete outlines with detailed descriptions.

## ✨ Key Features

- 🎨 **AI Image Generation** - Creates custom images using Google GenAI
- 📋 **Intelligent Modes** - Automatically detects IDEA, OUTLINE, GENERATION, or REVISION mode
- 📁 **File Detection** - Supports external outline and description files
- 🎯 **Visual Consistency** - Maintains consistent styling across all slides
- 📤 **Multiple Exports** - Export to PowerPoint (PPTX) and PDF formats
- 🔍 **Smart Prompts** - Enhanced prompt engineering for professional results

## 🚀 Quick Start

### Prerequisites

1. **Google API Key** for image generation:
   ```bash
   export GOOGLE_API_KEY="your-google-api-key"
   ```

   To get a Google API key:
   - Visit https://console.cloud.google.com/
   - Create a new project or select existing one
   - Enable 'Generative AI API' and 'Cloud Vision API'
   - Create credentials (API Key)
   - Set the environment variable

2. **OpenAI API Key** (for LLM):
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   ```

### Using the PPT Agent

```bash
# Start ArchiFlow
archiflow

# Create a PPT Agent session
/ppt                                    # Uses current directory
/ppt /path/to/presentations            # Uses specific directory

# Alternative method
/new ppt                               # Create via /new command
```

## 📋 Working Modes

The PPT Agent intelligently detects your mode based on input:

### 1. IDEA MODE
**When**: You provide only a topic or idea

**What happens**:
- Generates a comprehensive outline
- Creates detailed slide descriptions
- Generates images for each slide
- Exports to PPTX and PDF

**Example**:
```
Create a presentation about renewable energy
```

### 2. OUTLINE MODE
**When**: You provide an outline file

**What happens**:
- Loads your outline (JSON/Markdown)
- Generates detailed descriptions for each slide
- Creates consistent images
- Exports to PPTX and PDF

**Example**:
```
Use outline from my_outline.json to create presentation
```

### 3. GENERATION MODE
**When**: You provide both outline and description files

**What happens**:
- Directly generates images from descriptions
- Exports to PPTX and PDF
- Maintains visual consistency

**Example**:
```
Create presentation from outline.json and descriptions.json
```

### 4. REVISION MODE
**When**: You provide feedback on existing work

**What happens**:
- Updates outline or descriptions
- Regenerates affected images
- Re-exports presentations

**Example**:
```
Can you add more slides about solar energy?
```

## 📁 File Formats

### Outline Files
The agent supports these outline formats:

#### JSON Format
```json
{
  "title": "Your Presentation Title",
  "slides": [
    {
      "title": "Slide 1 Title",
      "content": ["Key point 1", "Key point 2"],
      "type": "title"
    },
    {
      "title": "Slide 2 Title",
      "content": ["Detail 1", "Detail 2", "Detail 3"],
      "type": "content"
    }
  ]
}
```

#### Markdown Format
```markdown
# Your Presentation Title

## Slide 1 Title
- Key point 1
- Key point 2

## Slide 2 Title
- Detail 1
- Detail 2
- Detail 3
```

### Description Files
Optional detailed descriptions for image generation:

```json
[
  {
    "slide_number": 1,
    "title": "Slide 1 Title",
    "image_prompt": "Detailed visual description...",
    "visual_style": "Clean, modern with blue accents",
    "slide_type": "title"
  }
]
```

## 🎨 Image Generation

The PPT Agent uses Google's Gemini 3 Pro Image Preview model to generate high-quality images:

### Supported Aspects
- **16:9** - Widescreen presentations (default)
- **4:3** - Standard presentations

### Supported Resolutions
- **2K** - High quality (2048x1152)
- **1024x768** - Standard quality
- **1920x1080** - Full HD

### Style Consistency
- First slide establishes the visual reference
- Subsequent slides maintain consistent styling
- Enhanced prompts ensure professional quality

## 📤 Output Files

The PPT Agent creates organized output:

```
data/
├── images/
│   └── {session_id}/
│       ├── slide_001.png
│       ├── slide_002.png
│       └── ...
└── ppt_exports/
    ├── {title}_20231220_143022.pptx
    └── {title}_20231220_143022.pdf
```

## 📖 Demo Example

See the `data/` directory for a complete example presentation about ArchiFlow:

### Generated Files:
- **[outline.json](../data/outline.json)** - Presentation outline
- **[descriptions.json](../data/descriptions.json)** - Detailed image descriptions
- **[Images](../data/images/)** - Generated slide images (slide_001.png through slide_008.png)
- **[Exports](../data/ppt_exports/)** - PPTX and PDF files

### Demo Content
The demo presentation showcases:
- ArchiFlow's event-driven architecture
- Multi-agent collaboration system
- Message queue design patterns
- Development lifecycle automation
- Production-ready features

### Try it yourself:
```bash
# Start PPT Agent
/ppt

# Use the existing descriptions
Create presentation from descriptions.json

# Or use the outline
Create presentation from outline.json
```

## ⚙️ Configuration

### Environment Variables
```bash
# Required
GOOGLE_API_KEY=your-google-api-key
OPENAI_API_KEY=your-openai-api-key

# Optional
PPT_AGENT_LOG_LEVEL=INFO          # Logging level
PPT_AGENT_MAX_TOKENS=4000         # Max tokens for LLM
PPT_AGENT_TEMPERATURE=0.7         # Creativity level
```

### Custom API Endpoints
```python
# For custom Google API endpoints
PPT_AGENT_GOOGLE_API_BASE=https://your-endpoint.com

# For custom OpenAI endpoints
OPENAI_API_BASE=https://your-endpoint.com
```

## 🛠️ Troubleshooting

### Common Issues

1. **"GOOGLE_API_KEY environment variable is required"**
   - Ensure you've set a valid Google API key
   - Verify the key has Generative AI API enabled

2. **"file uri and mime_type are required"**
   - This has been fixed in the latest version
   - Update to the current ArchiFlow version

3. **Poor image quality**
   - Be more specific in your image descriptions
   - Include style preferences (minimalist, corporate, colorful, etc.)
   - Use the REVISION mode to regenerate specific slides

4. **Export fails**
   - Check disk space in output directory
   - Ensure write permissions
   - Verify the output directory exists

### Debug Mode
Enable debug logging for detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](../CONTRIBUTING.md) for details.

### Development Setup
```bash
# Clone repository
git clone https://github.com/your-org/archiflow.git
cd archiflow

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/agent_framework/agents/test_ppt_agent.py -v
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## 🔗 Links

- [ArchiFlow Main README](../README.md)
- [API Documentation](../docs/API.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [Issue Tracker](https://github.com/your-org/archiflow/issues)

---

**Created with ❤️ by the ArchiFlow team**