import time,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent
log=root/"image_import_status.log"
for step in range(180):
    source=Path.home()/"Downloads"/"weex_bot_templates_ready.zip"
    if source.exists() and source.stat().st_size>10000:
        proc=subprocess.run([sys.executable,str(root/"install_images.py")],capture_output=True,text=True)
        log.write_text(proc.stdout+"\n"+proc.stderr,encoding="utf-8")
        break
    time.sleep(10)
else:
    log.write_text("Package not downloaded within watcher window",encoding="utf-8")
