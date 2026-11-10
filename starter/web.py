"""视图层：把任务列表渲染成 HTML 页面（字符串模板，无第三方依赖）。"""
from html import escape
from urllib.parse import urlencode
from service import STATUSES, filter_tasks, statistics
from config import APP_TITLE, APP_DESCRIPTION

FORM_KEYS = ("title", "owner", "due", "note", "status")

def e(value):
    return escape(str(value), quote=True)

def options(values, selected="", empty=False):
    result = '<option value="">全部</option>' if empty else ''
    return result + ''.join(f'<option value="{e(v)}" {"selected" if v == selected else ""}>{e(v)}</option>' for v in values)

def render(tasks, query, token):
    visible = filter_tasks(tasks, query.get("owner", ""), query.get("status", ""), query.get("keyword", ""))
    stats = statistics(tasks)
    edit = next((t for t in tasks if t["id"] == query.get("edit")), {})
    submitted = "form_title" in query  # 校验失败跳回时，用提交内容回填表单
    form = {key: query.get("form_" + key, "") for key in FORM_KEYS} if submitted else edit
    form_error = query.get("message", "") if submitted else ""
    action = "/update" if edit else "/add"
    stat_text = f'全部任务 {stats["total"]}　已完成 {stats["completed"]}　未完成 {stats["remaining"]}　完成率 {stats["percent"]}%'
    rows = ''
    for t in visible:
        link = '/?' + urlencode({"edit":t["id"]})
        rows += f'<tr><td><strong>{e(t["title"])}</strong><div class="note">{e(t["note"])}</div></td><td>{e(t["owner"])}</td><td>{e(t["due"])}</td><td>{e(t["status"])}</td><td><a href="{e(link)}">编辑 / 状态</a><form method="post" action="/delete" onsubmit="return confirm(\'确认删除这条任务？\')"><input type="hidden" name="token" value="{e(token)}"><input type="hidden" name="id" value="{e(t["id"])}"><button class="danger">删除</button></form></td></tr>'
    if not rows:
        rows = '<tr><td colspan="5">暂无匹配任务。可以添加任务或清除筛选。</td></tr>'
    form_error_html = f'<p class="message" role="alert">{e(form_error)}</p>' if form_error else ""
    top_message = "" if form_error else query.get("message", "")
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(APP_TITLE)}</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;background:#f5f7fa;color:#172d3e;margin:0}}main{{max-width:1100px;margin:auto;padding:36px 24px}}h1{{font-size:32px;margin:0}}h2{{font-size:21px}}section{{background:white;padding:24px;margin:24px 0;border:1px solid #dfe5eb}}label{{display:inline-block;margin:6px 14px 6px 0}}input,select,textarea,button{{font:inherit;padding:8px;border:1px solid #aebdc9;border-radius:4px}}textarea{{width:95%;height:65px}}button{{background:#145e78;color:white;cursor:pointer}}a{{color:#145e78}}table{{width:100%;border-collapse:collapse}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #ddd}}td form{{display:inline;margin-left:10px}}.note{{font-size:14px;color:#526675;white-space:pre-wrap;overflow-wrap:anywhere}}.danger{{background:white;color:#a02f32}}.message{{color:#9e3e16}}.stats{{font-weight:600}}@media(max-width:700px){{section{{overflow:auto}}}}</style>
<main><h1>{e(APP_TITLE)}</h1><p>{e(APP_DESCRIPTION)}</p><p class="message" role="status">{e(top_message)}</p><p class="stats">{stat_text}</p>
<section><h2>{'编辑任务' if edit else '添加任务'}</h2>{form_error_html}<form method="post" action="{action}">
<input type="hidden" name="token" value="{e(token)}"><input type="hidden" name="id" value="{e(edit.get('id',''))}">
<label>任务名称 <input name="title" value="{e(form.get('title',''))}"></label><label>负责人 <input name="owner" value="{e(form.get('owner',''))}"></label>
<label>截止日期 <input name="due" placeholder="YYYY-MM-DD" value="{e(form.get('due',''))}"></label><label>状态 <select name="status">{options(STATUSES,form.get('status') or edit.get('status') or STATUSES[0])}</select></label>
<label style="display:block">任务说明 <textarea name="note">{e(form.get('note',''))}</textarea></label><button>{'保存修改' if edit else '添加任务'}</button> <a href="/">取消编辑</a></form></section>
<section><h2>任务列表</h2><form method="get"><label>负责人 <select name="owner">{options(sorted(set(t['owner'] for t in tasks)),query.get('owner',''),True)}</select></label><label>状态 <select name="status">{options(STATUSES,query.get('status',''),True)}</select></label><label>关键词 <input name="keyword" value="{e(query.get('keyword',''))}" placeholder="名称或说明"></label><button>查询</button> <a href="/">清除筛选</a></form>
<table><thead><tr><th>任务</th><th>负责人</th><th>截止日期</th><th>状态</th><th>操作</th></tr></thead><tbody>{rows}</tbody></table></section></main></html>'''
