from pathlib import Path
import sys
print("Python:", sys.version.split()[0])
if sys.version_info < (3,11):
    raise SystemExit("请安装Python 3.11或以上版本")
base=Path(__file__).resolve().parent
probe=base/".write-check.tmp"
try:
    probe.write_text("ok",encoding="utf-8")
    probe.unlink()
except OSError as exc:
    raise SystemExit(f"目录无法写入，请解压到个人文件夹：{exc}")
print("项目目录:",base)
print("目录可写；本项目无需安装第三方包。")
