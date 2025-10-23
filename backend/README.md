Run backend:
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
POST /seed to seed data
Swagger: /docs
