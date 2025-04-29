# EasyGov Backend
A Django backend for EasyGov, summarizing government documents for UN SDGs 5 and 10.

## Setup
1. Clone the repo: `git clone <repo-url>`
2. Create a virtual environment: `python -m venv venv`
3. Activate: `source venv/bin/activate` (Windows: `venv\Scripts\activate`)
4. Install dependencies: `pip install -r requirements.txt`
5. Create `.env` file (see `.env` example above).
6. Run migrations: `python manage.py migrate`
7. Start server: `python manage.py runserver`

## API Endpoints
- GET `/api/health/`: Health check