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
