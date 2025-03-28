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
├── .spotify_cache_1
├── .spotify_cache_2
├── README.md
├── config.py
├── generate_readme.py
├── init_data.py
├── poetry.lock
├── pyproject.toml
├── requirements.txt
└── run.py
├── data/
│   ├── dataset_to_merge.csv
│   ├── merge_csvs.py
│   ├── tracks_features.csv
│   └── tracks_features_orig.csv
├── tests/
│   ├── __init__.py
│   ├── check_db.py
│   ├── debug_users.py
│   └── test_basic.py
├── app/
│   ├── __init__.py
│   ├── jinja_filters.py
│   └── models.py
│   ├── spotify_caches/
│   │   ├── temp_8OVqDZGogUQ_cache
│   │   ├── temp_KTkGPdXQWLU_cache
│   │   ├── temp_XmrmemRR_F4_cache
│   │   ├── temp_Z0GmY20tjKY_cache
│   │   ├── temp_c-BHH9sP-Eo_cache
│   │   ├── temp_ec0j7bOI4TI_cache
│   │   ├── temp_pihGgebam0E_cache
│   │   ├── temp_tQvXOVDil1E_cache
│   │   ├── temp_wTokxMEjMrY_cache
│   │   ├── temp_xhKNB7Kgh7c_cache
│   │   ├── user_1_cache
│   │   └── user_2_cache
│   ├── admin/
│   │   ├── __init__.py
│   │   ├── metrics_decorator.py
│   │   ├── metrics_routes.py
│   │   └── routes.py
│   ├── spotify/
│   │   ├── __init__.py
│   │   ├── csv_data_manager.py
│   │   ├── routes.py
│   │   └── utils.py
│   ├── templates/
│   │   └── base.html
│   │   ├── admin/
│   │   │   ├── beta_signups.html
│   │   │   └── metrics_dashboard.html
│   │   ├── spotify/
│   │   │   ├── visualize_artists.html
│   │   │   ├── visualize_audio_features.html
│   │   │   ├── visualize_generic.html
│   │   │   ├── visualize_saved_tracks.html
│   │   │   └── visualize_top_tracks.html
│   │   ├── randomizer/
│   │   │   ├── debug_result.html
│   │   │   ├── edit_config.html
│   │   │   ├── index.html
│   │   │   └── sync_playlists.html
│   │   ├── auth/
│   │   │   ├── beta_signup.html
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
│   │   │   ├── artists.js
│   │   │   ├── audio_features.js
│   │   │   ├── loading-helper.js
│   │   │   ├── saved_tracks.js
│   │   │   └── theme-manager.js
├── instance/
│   └── app.db
│   ├── user_data/
│   │   └── user_1.db
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

Text file: {"access_token": "BQDfcx6VAoYe_jYyJJRZ0sHsYAWy77CejsZFwG1cH7J8XnRnPwPFAfTMWARtTfIgCNrcYLUeNh6s18L63B...

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


### .spotify_cache_1

Text file: {"access_token": "BQC3YHCRl2-Gei48BSVBOwlExggpxsklGUX0ta97iz7jKcPtfnz5V9yFnlgaOzUD5pj1LoTY9y9zd_bl_H...

### .spotify_cache_2

Text file: {"access_token": "BQD0fidBq__qxWj5JH13w4v85IDOaEa_d6WHuJMhM4Vn2iaA7UIp3cMY1J447BKQIZ5Bb5HOB87RDkUc0t...

### README.md

Markdown documentation file

### config.py

Application configuration settings

### generate_readme.py

Generate a summary for the given file.

### init_data.py

Imports: app.models, app Defines functions: init_spotify_data_types

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

### data/dataset_to_merge.csv

File with .csv extension

### data/merge_csvs.py

Merge two CSV files based on common columns.

    Parameters:
    - small_csv_filename: Filename of the smaller CSV file with target columns
    - large_csv_filename: Filename of the larger CSV file to merge into
    - output_filename: Filename to save the merged CSV file
    - data_dir: Optional directory where CSV files are located (uses script dir by default)

### data/tracks_features.csv

File with .csv extension

### data/tracks_features_orig.csv

File with .csv extension

### tests/__init__.py

Package initialization file

### tests/check_db.py

Imports: flask_migrate, app Defines functions: check_database

### tests/debug_users.py

Imports: app.models, app, sys Defines functions: debug_users

### tests/test_basic.py

Python script with 1 lines

### app/__init__.py

Package initialization file

### app/jinja_filters.py

Custom Jinja2 filters for the application.
This module contains filters that can be registered with Flask to enhance templates.

### app/models.py

Database models defining: User, SpotifyDataType, UserDataSync, RandomizerConfig, RandomizerRule, PlaylistCreationHistory, BetaSignup

### app/spotify_caches/temp_8OVqDZGogUQ_cache

Text file: {"access_token": "BQD95-qq4KmbBBrVXdn4ZfHtJKYmlc0aLXgxJHm7AoKJBRdda-SbvmjwxCE-97XwfQ8A-L09tOT8GceaAq...

### app/spotify_caches/temp_KTkGPdXQWLU_cache

Text file: {"access_token": "BQDqsJsKQRFaIS93G0m4B0WNI3QxEjVW_vvqtUwrTsKgoPG5XojuTdUFfVqPAEyvCn0D39m-Qpl1Twx-vz...

### app/spotify_caches/temp_XmrmemRR_F4_cache

Text file: {"access_token": "BQBd_mkAtYWpqkWvJX1dEIctpp8FpqTb9SMLjzcaVKu_P9Rreilm8kPaQda-4pN4D0ApvwsNOjKmDXbcpT...

### app/spotify_caches/temp_Z0GmY20tjKY_cache

Text file: {"access_token": "BQAy5FCXKTiecFWUnRrczvwnZqlxVmHh8HS5-f7D--seRSLHKzY9QaG3yc5bt1zRUh-g68AfMWJ3YHkG_w...

### app/spotify_caches/temp_c-BHH9sP-Eo_cache

Text file: {"access_token": "BQCkThB2HP_cptM6qWWo1sw0fmsLsSTRlJPLRfhtpbVW30EQcjZvSM9T8EUZ2QO9rzKYNxEs5lar2KbFhh...

### app/spotify_caches/temp_ec0j7bOI4TI_cache

Text file: {"access_token": "BQBgVwuBdzgrObHKwHE7dfnCiO7ANpN1HB-OFGENLk44Rdbou43CKfyvtWQ8ksT3xJc8m51Yotyp4zWckJ...

### app/spotify_caches/temp_pihGgebam0E_cache

Text file: {"access_token": "BQANeo8B7dYmTNabzh3vy5igLmy5D3geo5oU_pL5yFxbiSj_5tb9ljjrvaxNULU7UCsfwFexxEjNce7FZ5...

### app/spotify_caches/temp_tQvXOVDil1E_cache

Text file: {"access_token": "BQDKrCg3mgA8Sn3PZd9NbmcH-C39ULqfq6DpHZySnXixKb8jY_m5AJ4u-jnNwK1tnJZq-xM-GczTMyL4WM...

### app/spotify_caches/temp_wTokxMEjMrY_cache

Text file: {"access_token": "BQDtAcKPGSqgGN8i3C5Vb3cxTtllcm_m65ncMF_tSgYm3VSe1levFCuh_GZjSgyqL51WJar00wU67dzMRt...

### app/spotify_caches/temp_xhKNB7Kgh7c_cache

Text file: {"access_token": "BQCKe93HGdzTYHttMT5A4KZ2xQPBG7daWYX_1c0sQ5hDf9isA5GkpLK_boSgYxnnem4QuhexaCKleTsQga...

### app/spotify_caches/user_1_cache

Text file: {"access_token": "BQDqsJsKQRFaIS93G0m4B0WNI3QxEjVW_vvqtUwrTsKgoPG5XojuTdUFfVqPAEyvCn0D39m-Qpl1Twx-vz...

### app/spotify_caches/user_2_cache

Text file: {"access_token": "BQAy5FCXKTiecFWUnRrczvwnZqlxVmHh8HS5-f7D--seRSLHKzY9QaG3yc5bt1zRUh-g68AfMWJ3YHkG_w...

### app/admin/__init__.py

Package initialization file

### app/admin/metrics_decorator.py

Imports 8 modules Defines classes: FunctionMetrics Defines 11 functions

### app/admin/metrics_routes.py

Route handlers for: /metrics, /metrics/data, /metrics/reset, /metrics/reset/<func_name>

### app/admin/routes.py

Route handlers for: /beta-signups, /export-signups/<format>

### app/spotify/__init__.py

Package initialization file

### app/spotify/csv_data_manager.py

Imports 6 modules Defines classes: TrackFeaturesManager Defines 9 functions

### app/spotify/routes.py

Route handlers for: /progress/<operation_id>, /connect, /callback, /disconnect, /sync/<data_type>, /visualize/<data_type>, /get_playlists

### app/spotify/utils.py

Get an authenticated Spotify client for a user

### app/templates/base.html

Base template providing layout structure for the application

### app/templates/admin/beta_signups.html

 template extending base.html

### app/templates/admin/metrics_dashboard.html

 dashboard template extending base.html

### app/templates/spotify/visualize_artists.html

Spotify template extending base.html

### app/templates/spotify/visualize_audio_features.html

Spotify template extending base.html

### app/templates/spotify/visualize_generic.html

Spotify template extending base.html

### app/templates/spotify/visualize_saved_tracks.html

Spotify template extending base.html

### app/templates/spotify/visualize_top_tracks.html

Spotify template extending base.html

### app/templates/randomizer/debug_result.html

 template extending base.html

### app/templates/randomizer/edit_config.html

 template extending base.html

### app/templates/randomizer/index.html

 index/home template extending base.html

### app/templates/randomizer/sync_playlists.html

 template extending base.html

### app/templates/auth/beta_signup.html

Authentication template extending base.html

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

Route handlers for: /randomizer, /create_playlist, /get_config_rules/<int:id>, /edit_config/<int:id>, /delete_config/<int:id>, /sync_playlists, /debug_playlist

### app/randomizer/rule_processor.py

Categorize rules by type and processing order

### app/auth/__init__.py

Package initialization file

### app/auth/forms.py

Flask forms: LoginForm, RegistrationForm, BetaSignupForm

### app/auth/routes.py

Route handlers for: /login, /callback, /login/callback, /logout, /profile, /beta-signup

### app/main/__init__.py

Package initialization file

### app/main/routes.py

Route handlers for: /, /index, /about, /dashboard

### app/static/favicon.ico

Binary file or encoding issues

### app/static/css/style.css

CSS file with 24 style definitions

### app/static/images/spiffy-logo.png

Binary file or encoding issues

### app/static/js/artists.js

File with .js extension

### app/static/js/audio_features.js

File with .js extension

### app/static/js/loading-helper.js

File with .js extension

### app/static/js/saved_tracks.js

File with .js extension

### app/static/js/theme-manager.js

File with .js extension

### instance/app.db

Binary file or encoding issues

### instance/user_data/user_1.db

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

Generated on: 2025-03-28
