import shutil
import os

images = {
    '/Users/veerapandig/.gemini/antigravity-ide/brain/9b4b678d-0f18-4c6f-8036-6b16714172cb/service_cybersecurity_1780782446913.png': 'frontend/assets/images/service_cybersecurity.png',
    '/Users/veerapandig/.gemini/antigravity-ide/brain/9b4b678d-0f18-4c6f-8036-6b16714172cb/service_project_dev_1780782700619.png': 'frontend/assets/images/service_project_dev.png',
    '/Users/veerapandig/.gemini/antigravity-ide/brain/9b4b678d-0f18-4c6f-8036-6b16714172cb/work_security_audit_1780780432041.png': 'frontend/assets/images/work_security_audit.png',
    '/Users/veerapandig/.gemini/antigravity-ide/brain/9b4b678d-0f18-4c6f-8036-6b16714172cb/hero_cyber_theme_1780782222452.png': 'frontend/assets/images/hero_bg.png'
}

for src, dst in images.items():
    try:
        shutil.copy(src, dst)
        print(f"✅ Copied to {dst}")
    except Exception as e:
        print(f"❌ Failed to copy {os.path.basename(src)}: {e}")
