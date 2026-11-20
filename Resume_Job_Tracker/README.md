# Resume & Job Application Kanban Tracker

A Flask + SQLite application for organizing job applications and resume versions.

## Features
- Account registration and login with hashed passwords
- Dashboard metrics and upcoming follow-up dates
- Kanban workflow: Wishlist, Applied, Assessment, Interview, Offer, Rejected
- Drag-and-drop status updates
- Add, edit, search and delete job applications
- Upload/download/delete PDF, DOC and DOCX resumes (8 MB max)
- Profile name and dark/light theme preference

## Run on Windows
1. Install Python 3.10 or newer.
2. Open this folder in VS Code.
3. Open Terminal and run:

   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
   ```

4. Open http://127.0.0.1:5000

The SQLite database is created automatically at `instance/tracker.db`.

## Notes
- Uploaded resumes are stored in `static/uploads/`.
- This starter is intended for local development. Before public deployment, set a strong `SECRET_KEY`, disable Flask debug mode, add CSRF protection, and configure secure production file storage.
