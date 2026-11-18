@echo off
rem Double-click to install what the tool needs, start it, and open it in the browser.
cd /d "%~dp0"
python -m pip install -q --disable-pip-version-check -r requirements.txt || (echo Python 3.12 is needed: https://www.python.org/downloads/ & pause & exit /b 1)
python -m streamlit run streamlit_app.py
pause
