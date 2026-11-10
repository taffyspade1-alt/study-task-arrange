"""数据持久化：读写 data/tasks.json，采用临时文件 + 原子替换，避免写入中断损坏数据。"""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

DATA_PATH = Path(__file__).resolve().parent / "data" / "tasks.json"

def load_tasks(path=DATA_PATH):
    # 文件不存在按首次运行处理；只读取，损坏时抛错并保留原文件。
    if not Path(path).exists():
        return []
    try:
        with open(path, encoding="utf-8") as file:
            tasks = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"数据文件已损坏：{path}（第{exc.lineno}行）。请先备份该文件，再修复或删除后重新启动。") from exc
    except OSError as exc:
        raise ValueError(f"无法读取数据文件：{path}（{exc}）") from exc
    if not isinstance(tasks, list):
        raise ValueError(f"数据文件格式不正确：{path} 最外层必须是任务列表。请先备份该文件再处理。")
    return tasks

def save_tasks(tasks, path=DATA_PATH):
    # 先写同目录临时文件再整体替换，中途失败不会破坏原文件。
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as file:
            temp = Path(file.name)
            json.dump(tasks, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
        temp = None
    except TypeError as exc:
        raise ValueError(f"任务内容无法保存为JSON：{exc}") from exc
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
