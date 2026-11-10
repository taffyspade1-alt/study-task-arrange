"""本地启动入口：启动 HTTP 服务并绑定 127.0.0.1，不对公网开放。"""
import argparse
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse, urlencode
from service import add_task, update_task, delete_task
from storage import load_tasks, save_tasks
from web import render

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        tasks = load_tasks()
    except ValueError as exc:
        print(exc)
        return 1
    token = secrets.token_urlsafe(24)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != "/":
                self.send_error(404)
                return
            query = {k:v[0] for k,v in parse_qs(parsed.query,keep_blank_values=True).items()}
            content = render(tasks, query, token).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        def do_POST(self):
            nonlocal tasks
            data = {}
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= 100000:
                    raise ValueError("提交内容过大")
                data = {k:v[0] for k,v in parse_qs(self.rfile.read(length).decode("utf-8"),keep_blank_values=True).items()}
                if not secrets.compare_digest(data.get("token", ""), token):
                    raise ValueError("页面已过期，请刷新后重试")
                if self.path == "/add":
                    updated = add_task(tasks, data)
                elif self.path == "/update":
                    updated = update_task(tasks, data.get("id"), data)
                elif self.path == "/delete":
                    updated = delete_task(tasks, data.get("id"))
                else:
                    raise ValueError("未知操作")
                save_tasks(updated)
                tasks = updated
                params = {"message": "操作完成，请核对结果"}
            except (ValueError, NotImplementedError, OSError) as exc:
                params = {"message": str(exc)}
                if self.path in ("/add", "/update"):
                    # 校验失败时把刚提交的内容带回页面，避免用户重新输入。
                    for key in ("title", "owner", "due", "note", "status"):
                        params[f"form_{key}"] = data.get(key, "")
                    if self.path == "/update" and data.get("id"):
                        params["edit"] = data.get("id")
            self.send_response(303)
            self.send_header("Location", "/?" + urlencode(params))
            self.end_headers()
        def log_message(self, fmt, *args):
            print(fmt % args)
    try:
        server = HTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        print(f"启动失败：{exc}。端口被占用时可使用 --port 8766")
        return 1
    print(f"浏览器打开 http://127.0.0.1:{args.port} 。终端按Ctrl+C停止。", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("已停止")
    finally:
        server.server_close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
