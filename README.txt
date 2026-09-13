KENGURU ADMIN PRO UPDATE

Upload these 5 files to the ROOT of the GitHub repository:
- admin.html (replace existing)
- requirements.txt (replace existing)
- admin_extra.py (new)
- pgcompat.py (new)
- sitecustomize.py (new)

Do NOT delete main.py, app.js, index.html, style.css, logo.jpg or template PNG files.

After upload, Render redeploys. For persistent PostgreSQL:
Set DATABASE_URL in the web service Environment to the Internal Database URL of
Render database: kenguru-olympiad-db.

Admin PRO features:
- participants/payments/results
- CSV export
- participant deletion
- edit questions by grade
- upload diploma/certificate PNG templates
- persistent participants/questions/templates when DATABASE_URL is configured.
