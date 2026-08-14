Minimal project skeleton created.

Backend (Flask):
- Run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python backend\app.py
```

Frontend (static):
- Serve the `frontend` folder (from workspace root) for example:

```powershell
# from workspace root
cd frontend
python -m http.server 3000
# then open http://localhost:3000/public/index.html
```

Backup of previous project: `D:\SIP_backup_20260814_225136.zip`

Database configuration
----------------------
- Set the MongoDB connection string in `backend/.env` as the `MONGO_URI` variable.
- Example (URL-encode special characters in the password):

```
MONGO_URI="mongodb+srv://shaikmehfuz07_db_user:<URL-ENCODED_PASSWORD>@cluster0.02eoqkv.mongodb.net/interview_prep?retryWrites=true&w=majority"
```
- Do NOT commit `backend/.env` to source control. It's already ignored in `.gitignore`.
