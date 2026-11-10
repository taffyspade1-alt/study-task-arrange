"""业务逻辑：字段校验、增删改、筛选与统计。纯函数，不依赖文件系统。"""
import re
from copy import deepcopy
from datetime import date
from uuid import uuid4

STATUSES = ("待开始", "进行中", "已完成")
DUE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")  # 只认四位年-两位月-两位日

def validate(data):
    # 校验一条任务的全部字段。任何一项不合格都抛错，调用方不得保存。
    values = {key: str(data.get(key, "")) for key in ("title", "owner", "due", "note", "status")}
    title = values["title"].strip()
    owner = values["owner"].strip()
    due = values["due"].strip()
    status = values["status"].strip()
    if not title:
        raise ValueError("任务名称不能为空（去掉首尾空格后仍需填写）")
    if not owner:
        raise ValueError("负责人不能为空（去掉首尾空格后仍需填写）")
    if not DUE_PATTERN.fullmatch(due):
        raise ValueError(f"截止日期格式应为YYYY-MM-DD，例如2026-09-30（收到“{due}”）")
    try:
        date.fromisoformat(due)  # 上面只保证长这样，这里再确认是真实存在的一天
    except ValueError as exc:
        raise ValueError(f"截止日期“{due}”不是真实存在的日期，请检查月份和天数") from exc
    if status not in STATUSES:
        raise ValueError("状态只能是：" + "、".join(STATUSES))
    return {"title": title, "owner": owner, "due": due, "note": values["note"], "status": status}

def add_task(tasks, data):
    # 添加后返回新的完整任务列表；未填状态时按“待开始”处理。
    payload = dict(data)
    if not str(payload.get("status", "")).strip():
        payload["status"] = STATUSES[0]
    task = {"id": str(uuid4()), **validate(payload)}
    return deepcopy(tasks) + [task]

def update_task(tasks, task_id, data):
    # 支持全字段更新。先整体校验再改副本，任何一步失败都不会动到原任务。
    values = validate(data)
    result = deepcopy(tasks)
    for task in result:
        if task["id"] == task_id:
            task.update(values)
            return result
    raise ValueError("找不到这条任务，请刷新页面后重试")

def delete_task(tasks, task_id):
    # 页面已在提交前弹出确认，取消时不会调用本函数。这里只负责删除并返回新的列表。
    result = deepcopy(tasks)
    for index, task in enumerate(result):
        if task["id"] == task_id:
            del result[index]
            return result
    raise ValueError("找不到这条任务，请刷新页面后重试")

def filter_tasks(tasks, owner="", status="", keyword=""):
    # 负责人、状态按完整值比较，关键词在 title 或 note 中找；多个条件要同时满足。
    # 三个条件都忽略首尾空格，留空表示这一项不筛。返回副本，原始列表和原始任务都不动。
    owner = str(owner or "").strip()
    status = str(status or "").strip()
    keyword = str(keyword or "").strip()
    result = []
    for task in tasks:
        if owner and str(task.get("owner", "")) != owner:
            continue
        if status and str(task.get("status", "")) != status:
            continue
        if keyword and keyword not in str(task.get("title", "")) and keyword not in str(task.get("note", "")):
            continue
        result.append(task)
    return deepcopy(result)  # 保留 id 等全部字段，筛选结果可以直接拿去编辑

def statistics(tasks):
    # 统计始终针对全部任务；筛选只改变下方列表，不影响这里。
    total = len(tasks)
    completed = sum(1 for task in tasks if task.get("status") == "已完成")
    remaining = total - completed
    percent = round(completed / total * 100, 1) if total else 0
    return {"total": total, "completed": completed, "remaining": remaining, "percent": percent}
