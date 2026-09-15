from pathlib import Path

path = Path("src/growwise/api/main.py")
text = path.read_text(encoding="utf-8")
old_import = "from growwise.api.backup_routes import router as backup_router\n"
new_import = (
    "from growwise.api.backup_routes import router as backup_router\n"
    "from growwise.api.study_routes import router as study_router\n"
)
if old_import not in text:
    raise RuntimeError("backup router import anchor not found")
text = text.replace(old_import, new_import, 1)
old_include = "app.include_router(backup_router)\n"
new_include = "app.include_router(backup_router)\napp.include_router(study_router)\n"
if old_include not in text:
    raise RuntimeError("backup router include anchor not found")
text = text.replace(old_include, new_include, 1)
path.write_text(text, encoding="utf-8")
