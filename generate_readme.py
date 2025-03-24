import os
import re
import inspect
from datetime import datetime


def get_file_summary(file_path):
    """Generate a summary for the given file."""
    if not os.path.exists(file_path):
        return "File not found"

    with open(file_path, "r", encoding="utf-8") as file:
        try:
            content = file.read()
        except UnicodeDecodeError:
            return "Binary file or encoding issues"

    # Get file extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    # Define summary based on file type
    if ext == ".py":
        return summarize_python_file(content, file_path)
    elif ext in [".html", ".htm"]:
        return summarize_html_file(content, file_path)
    elif ext == ".css":
        return summarize_css_file(content)
    elif ext == ".md":
        return "Markdown documentation file"
    elif ext in [".txt", ""]:
        return f"Text file: {content[:100]}..." if len(content) > 100 else content
    elif ext == ".env":
        return "Environment variables configuration"
    else:
        return f"File with {ext} extension"


def summarize_python_file(content, file_path):
    """Generate a summary for a Python file."""
    # Extract docstring if present
    docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
    docstring = docstring_match.group(1).strip() if docstring_match else ""

    # Extract imports
    imports = re.findall(
        r"^import\s+(.+?)$|^from\s+(.+?)\s+import", content, re.MULTILINE
    )
    imports = [imp[0] or imp[1] for imp in imports]

    # Check for specific file patterns
    filename = os.path.basename(file_path)

    if filename == "__init__.py":
        return "Package initialization file"
    elif filename == "models.py":
        classes = re.findall(r"class\s+(\w+)", content)
        return f"Database models defining: {', '.join(classes)}"
    elif "routes.py" in filename:
        routes = re.findall(r'@.*?route\([\'"](.+?)[\'"]', content)
        bp_name = re.search(r'bp = Blueprint\([\'"](.+?)[\'"]', content)
        bp_str = f" for {bp_name.group(1)} blueprint" if bp_name else ""
        return f"Route handlers{bp_str} for: {', '.join(routes)}"
    elif "forms.py" in filename:
        forms = re.findall(r"class\s+(\w+Form)", content)
        return f"Flask forms: {', '.join(forms)}"
    elif "config.py" in filename:
        return "Application configuration settings"
    elif "app.py" in filename or "run.py" in filename:
        return "Main application entry point"

    # Generic summary based on content
    if docstring:
        return docstring

    classes = re.findall(r"class\s+(\w+)", content)
    functions = re.findall(r"def\s+(\w+)", content)

    summary = []
    if imports:
        unique_imports = set(imports)
        if len(unique_imports) <= 5:
            summary.append(f"Imports: {', '.join(unique_imports)}")
        else:
            summary.append(f"Imports {len(unique_imports)} modules")

    if classes:
        summary.append(f"Defines classes: {', '.join(classes)}")

    if functions:
        if len(functions) <= 5:
            summary.append(f"Defines functions: {', '.join(functions)}")
        else:
            summary.append(f"Defines {len(functions)} functions")

    if not summary:
        lines = content.count("\n") + 1
        summary.append(f"Python script with {lines} lines")

    return " ".join(summary)


def summarize_html_file(content, file_path):
    """Generate a summary for an HTML file."""
    # Extract title
    title_match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE)
    title = title_match.group(1) if title_match else ""

    # Determine template type based on path or content
    filename = os.path.basename(file_path)

    if "{% extends" in content:
        extends_match = re.search(r'{%\s*extends\s+[\'"](.+?)[\'"]', content)
        base_template = extends_match.group(1) if extends_match else "base template"

        # Identify template purpose based on folder or filename
        template_type = ""
        if "auth" in file_path:
            template_type = "Authentication"
        elif "main" in file_path:
            template_type = "Main"
        elif "spotify" in file_path:
            template_type = "Spotify"

        if "login" in filename:
            template_type = f"{template_type} login"
        elif "register" in filename:
            template_type = f"{template_type} registration"
        elif "profile" in filename:
            template_type = f"{template_type} user profile"
        elif "dashboard" in filename:
            template_type = f"{template_type} dashboard"
        elif "index" in filename:
            template_type = f"{template_type} index/home"

        return f"{template_type} template extending {base_template}" + (
            f" with title: {title}" if title else ""
        )

    if "base.html" in filename:
        return "Base template providing layout structure for the application"

    # Fallback
    return f"HTML template" + (f" with title: {title}" if title else "")


def summarize_css_file(content):
    """Generate a summary for a CSS file."""
    selectors = re.findall(r"([.#]?\w+(?:[-_]\w+)*)\s*{", content)
    style_count = len(selectors)

    if style_count == 0:
        return "Empty CSS file"
    elif style_count <= 10:
        return f"CSS styling for: {', '.join(selectors)}"
    else:
        return f"CSS file with {style_count} style definitions"


def generate_file_tree(start_path, exclude_patterns=None):
    """Generate a text representation of the file tree."""
    if exclude_patterns is None:
        exclude_patterns = [
            r"__pycache__",
            r"\.git",
            r"\.idea",
            r"\.vscode",
            r"\.pytest_cache",
            r"venv",
            r".venv",
            r"env",
            r"node_modules",
            r"\.pyc$",
            r"\.pyo$",
            r"\.mo$",
            r"\.o$",
            r"\.so$",
            r"\.exe$",
            r"icons",
            r"migrations",
        ]

    lines = []

    for root, dirs, files in os.walk(start_path):
        # Skip excluded directories
        dirs[:] = [
            d
            for d in dirs
            if not any(re.match(pattern, d) for pattern in exclude_patterns)
        ]

        # Calculate the current level to determine indentation
        level = root.replace(start_path, "").count(os.sep)
        indent = "│   " * level

        # Add directory name
        if level > 0:
            lines.append(f"{indent[:-4]}├── {os.path.basename(root)}/")
        else:
            lines.append(
                f"{os.path.basename(root) or os.path.basename(os.path.abspath(start_path))}/"
            )

        # Add files
        for i, file in enumerate(sorted(files)):
            if any(re.search(pattern, file) for pattern in exclude_patterns):
                continue

            is_last = i == len(files) - 1
            file_indent = indent + ("└── " if is_last else "├── ")
            lines.append(f"{file_indent}{file}")

    return "\n".join(lines)


def generate_readme():
    """Generate the full README.md content."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    project_name = os.path.basename(project_root)

    # Project tree
    file_tree = generate_file_tree(project_root)

    # File descriptions
    file_descriptions = []

    for root, _, files in os.walk(project_root):
        # Skip certain directories
        if any(
            p in root
            for p in [
                "__pycache__",
                ".git",
                "venv",
                ".venv",
                "env",
                "node_modules",
                "assets",
                ".idea",
                "migrations",
            ]
        ):
            continue

        for file in sorted(files):
            if file.endswith((".pyc", ".git", ".idea", ".vscode")):
                continue

            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, project_root)

            try:
                summary = get_file_summary(file_path)
                file_descriptions.append(f"### {rel_path}\n\n{summary}\n")
            except Exception as e:
                file_descriptions.append(
                    f"### {rel_path}\n\nError generating summary: {str(e)}\n"
                )

    # Generate README content
    readme_content = f"""# {project_name}

A Flask web application that connects to the Spotify API and allows users to explore and visualize their Spotify data.

## Overview

This application uses the Spotify OAuth flow to authenticate users directly with their Spotify accounts. It allows users to:

1. Log in with their Spotify credentials
2. View and analyze their top tracks, artists, playlists, and listening history
3. Visualize music data in various charts and graphs
4. Store their Spotify data in a local SQLite database

## Project Structure

```
{file_tree}
```

## Key Components

1. **Authentication**: Uses Spotify OAuth for user authentication
2. **Data Storage**: Stores user data in SQLite databases
3. **Data Visualization**: Displays Spotify data using Chart.js
4. **API Integration**: Uses the Spotipy library to interact with Spotify's API

## File Descriptions

{chr(10).join(file_descriptions)}

## Setup Instructions

1. Create a Spotify Developer account and register an application
2. Set up the redirect URI as `http://localhost:5000/callback`
3. Create a `.env` file with your Spotify credentials:
   ```
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   SPOTIFY_REDIRECT_URI=http://localhost:5000/callback
   SECRET_KEY=your_secret_key
   ```
4. Install dependencies:
   ```bash
   pip install flask flask-sqlalchemy flask-migrate flask-login python-dotenv spotipy
   ```
5. Initialize the database:
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   python init_data.py
   ```
6. Run the application:
   ```bash
   flask run
   ```

## Credits

This application was created using Flask, Spotipy, and other open-source libraries.

Generated on: {datetime.now().strftime('%Y-%m-%d')}
"""

    # Write to README.md
    readme_path = os.path.join(project_root, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print(f"README.md has been generated at {readme_path}")


if __name__ == "__main__":
    generate_readme()
