# spiffy

A Flask web application that connects to the Spotify API and allows users to explore and visualize their Spotify data.

## Overview

This application uses the Spotify OAuth flow to authenticate users directly with their Spotify accounts. It allows users to:

1. Log in with their Spotify credentials
2. View and analyze their top tracks, artists, playlists, and listening history
3. Visualize music data in various charts and graphs
4. Store their Spotify data in a local SQLite database

## Project Structure

```
spiffy/
├── .cache
├── .python-version
├── README.md
├── config.py
├── generate_readme.py
├── init_data.py
├── poetry.lock
├── pyproject.toml
├── requirements.txt
└── run.py
├── tests/
│   ├── __init__.py
│   ├── check_db.py
│   ├── debug_users.py
│   └── test_basic.py
├── app/
│   ├── __init__.py
│   └── models.py
│   ├── spotify/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── utils.py
│   ├── templates/
│   │   └── base.html
│   │   ├── spotify/
│   │   │   ├── visualize_generic.html
│   │   │   ├── visualize_saved_tracks.html
│   │   │   └── visualize_top_tracks.html
│   │   ├── randomizer/
│   │   │   ├── edit_config.html
│   │   │   ├── index.html
│   │   │   └── sync_playlists.html
│   │   ├── auth/
│   │   │   ├── login.html
│   │   │   ├── profile.html
│   │   │   └── register.html
│   │   ├── main/
│   │   │   ├── about.html
│   │   │   ├── dashboard.html
│   │   │   └── index.html
│   ├── randomizer/
│   │   ├── __init__.py
│   │   ├── forms.py
│   │   ├── helpers.py
│   │   ├── routes.py
│   │   └── rule_processor.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── forms.py
│   │   └── routes.py
│   ├── main/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── static/
│   │   └── favicon.ico
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── images/
│   │   │   └── spiffy-logo.png
│   │   ├── js/
│   │   │   ├── loading-helper.js
│   │   │   └── saved_tracks.js
├── instance/
│   └── app.db
│   ├── user_data/
│   │   └── user_None.db
├── logs/
│   └── spotify_explorer.log
├── assets/
│   ├── docs/
│   │   └── Loading Modal.md
```

## Key Components

1. **Authentication**: Uses Spotify OAuth for user authentication
2. **Data Storage**: Stores user data in SQLite databases
3. **Data Visualization**: Displays Spotify data using Chart.js
4. **API Integration**: Uses the Spotipy library to interact with Spotify's API

## File Descriptions

### .cache

Text file: {"access_token": "BQDpLF2Q-JIhzsF-ef-kHsg7P3y-XxBskBzGkCZ8eKQFin1fbHU4Hn22DZnIR89fIUSXy1A4gs22yU3dMv...

### .env

Text file: SPOTIFY_CLIENT_ID=46265ff9a5634152b08ff65c204f38a4
SPOTIFY_CLIENT_SECRET=62a9086b35d74b2389e2604c19e...

### .flaskenv



### .gitignore

Text file: .env
.cache
.venv
.idea
poetry.lock
.flaskenv
migrations
__pycache__/
*.pyc
*.pyo
*.pyd
*.db
*.sqlit...

### .python-version

3.12.1


### README.md

Markdown documentation file

### config.py

Application configuration settings

### generate_readme.py

Generate a summary for the given file.

### init_data.py

Imports: app, app.models Defines functions: init_spotify_data_types

### poetry.lock

File with .lock extension

### pyproject.toml

File with .toml extension

### requirements.txt

Text file: alembic==1.15.1
black==25.1.0
blinker==1.9.0
certifi==2025.1.31
charset-normalizer==3.4.1
click==8.1...

### run.py

Main application entry point

### tests/__init__.py

Package initialization file

### tests/check_db.py

Imports: flask_migrate, app Defines functions: check_database

### tests/debug_users.py

Imports: sys, app, app.models Defines functions: debug_users

### tests/test_basic.py

Python script with 1 lines

### app/__init__.py

Package initialization file

### app/models.py

Database models defining: User, SpotifyDataType, UserDataSync, RandomizerConfig, RandomizerRule, PlaylistCreationHistory

### app/spotify/__init__.py

Package initialization file

### app/spotify/routes.py

Route handlers for: /connect, /callback, /disconnect, /sync/<data_type>, /visualize/<data_type>, /get_playlists

### app/spotify/utils.py

Get an authenticated Spotify client for a user

### app/templates/base.html

Base template providing layout structure for the application

### app/templates/spotify/visualize_generic.html

Spotify template extending base.html

### app/templates/spotify/visualize_saved_tracks.html

Spotify template extending base.html

### app/templates/spotify/visualize_top_tracks.html

Spotify template extending base.html

### app/templates/randomizer/edit_config.html

 template extending base.html

### app/templates/randomizer/index.html

 index/home template extending base.html

### app/templates/randomizer/sync_playlists.html

 template extending base.html

### app/templates/auth/login.html

Authentication login template extending base.html

### app/templates/auth/profile.html

Authentication user profile template extending base.html

### app/templates/auth/register.html

Authentication registration template extending base.html

### app/templates/main/about.html

Main template extending base.html

### app/templates/main/dashboard.html

Main dashboard template extending base.html

### app/templates/main/index.html

Main index/home template extending base.html

### app/randomizer/__init__.py

Package initialization file

### app/randomizer/forms.py

Flask forms: RuleForm, RandomizerConfigForm

### app/randomizer/helpers.py

Extract rules from form data, supporting multiple formats

### app/randomizer/routes.py

Route handlers for: /randomizer, /create_playlist, /get_config_rules/<int:id>, /edit_config/<int:id>, /delete_config/<int:id>, /sync_playlists

### app/randomizer/rule_processor.py

Categorize rules by type and processing order

### app/auth/__init__.py

Package initialization file

### app/auth/forms.py

Flask forms: LoginForm, RegistrationForm

### app/auth/routes.py

Route handlers for: /login, /callback, /login/callback, /logout, /profile

### app/main/__init__.py

Package initialization file

### app/main/routes.py

Route handlers for: /, /index, /about, /dashboard

### app/static/favicon.ico

Binary file or encoding issues

### app/static/css/style.css

CSS file with 14 style definitions

### app/static/images/spiffy-logo.png

Binary file or encoding issues

### app/static/js/loading-helper.js

File with .js extension

### app/static/js/saved_tracks.js

File with .js extension

### instance/app.db

Binary file or encoding issues

### instance/user_data/user_None.db

Binary file or encoding issues

### logs/spotify_explorer.log

File with .log extension


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

Generated on: 2025-03-25
