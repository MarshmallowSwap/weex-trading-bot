from pathlib import Path
import zipfile,shutil,time,sys
root=Path(r"D:\FUNDSHOT\hyperliquid_alerts")
dest=root/"templates"
downloads=Path.home()/"Downloads"
backup=Path(r"D:\FUNDSHOT\weex_alerts")/"templates_backup_hyperliquid"
wanted=("long.jpg","short.jpg","profit.jpg","loss.jpg","pnl.jpg","winrate.jpg")
def run():
  files=sorted(downloads.glob("weex_bot_templates_ready*.zip"),key=lambda p:p.stat().st_mtime,reverse=True)
  if not files:
    print("WAITING_FOR_WEEX_ZIP")
    return 2
  archive=files[0]
  with zipfile.ZipFile(archive) as z:
    available=set(z.namelist())
    if not set(wanted).issubset(available):
      raise RuntimeError("Missing template files")
    from PIL import Image
    from io import BytesIO
    for n in wanted:
      im=Image.open(BytesIO(z.read(n)))
      if im.width/im.height < 1.7 or im.width/im.height>1.9:
        raise ValueError("Template aspect ratio invalid: "+n)
    backup.mkdir(exist_ok=True,parents=True)
    for n in wanted:
      old=dest/n
      if old.exists() and not (backup/n).exists(): shutil.copy2(old,backup/n)
    for n in wanted:
      temp=dest/(n+".tmp")
      temp.write_bytes(z.read(n))
      temp.replace(dest/n)
    profile=Path(r"D:\FUNDSHOT\weex_alerts")/"profile_hypergrok_weex.png"
    profile.write_bytes(z.read("profile_hypergrok_weex.png"))
  print("WEEX_TEMPLATES_INSTALLED",len(wanted))
  sys.path.insert(0,str(root))
  from cards import render
  for kind in ("long","short","profit","loss","pnl","winrate"):
    data=render(kind,[("TEST","WEEX"),("TEST","1.0"),("TEST","N/D"),("TEST","123.45"),("TEST","30 GG")])
    print("RENDER_PASS",kind,len(data))
  return 0
if __name__=="__main__":sys.exit(run())

