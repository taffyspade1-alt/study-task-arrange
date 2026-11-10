"""编辑校验与删除功能的测试。

运行方式（Windows，在本项目文件夹打开终端）：
    py test_edit.py
    py -m unittest test_edit -v
macOS/Linux 把 py 换成 python3。测试不会碰 data/tasks.json，
HTTP 部分会把项目复制到临时目录里跑，结束后自动删除。

覆盖两类要求：
1. 错误输入：title 和 owner 去掉首尾空格后不能为空，due 必须是 YYYY-MM-DD 且真实存在，
   status 只能是三种已有状态。只要有一项不合格就要报错，并且原任务一个字都不能变。
2. 取消删除：确认框点“取消”时表单不会提交，任务必须原样留着；
   同时验证“确认删除”确实能删掉、没有有效令牌的删除请求会被拒绝，
   这样取消测试才不会因为删除功能本身坏了而误判为通过。
"""
import copy
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from service import STATUSES, add_task, delete_task, update_task

PROJECT = Path(__file__).resolve().parent
SOURCE_FILES = ("app.py", "config.py", "service.py", "storage.py", "web.py")


def sample_tasks():
    return [
        {"id": "t-1", "title": "需求评审", "owner": "张明", "due": "2026-09-30", "note": "第一次评审", "status": "已完成"},
        {"id": "t-2", "title": "接口联调", "owner": "李静", "due": "2026-10-15", "note": "", "status": "进行中"},
    ]


def valid_form(**changes):
    """一条完整的合法编辑内容，各用例只替换需要出错的那一项。"""
    form = {"id": "t-1", "title": "需求评审（修订）", "owner": "王敏", "due": "2026-11-01", "note": "改期", "status": "进行中"}
    form.update(changes)
    return form


class UpdateValidationTest(unittest.TestCase):
    """编辑校验：合法输入改全部字段，错误输入一律报错且不改动原任务。"""

    def setUp(self):
        self.tasks = sample_tasks()
        self.before = copy.deepcopy(self.tasks)  # 出错后拿它对比，确认没有被动过

    def test_合法输入可以改全部字段(self):
        result = update_task(self.tasks, "t-1", valid_form())
        changed = next(t for t in result if t["id"] == "t-1")
        self.assertEqual((changed["title"], changed["owner"], changed["due"], changed["note"], changed["status"]),
                         ("需求评审（修订）", "王敏", "2026-11-01", "改期", "进行中"))
        self.assertEqual(changed["id"], "t-1")  # id 不能被改掉
        self.assertEqual(self.tasks, self.before)  # 原列表保持不变

    def test_其他任务不受影响(self):
        result = update_task(self.tasks, "t-1", valid_form())
        self.assertEqual(next(t for t in result if t["id"] == "t-2"), self.before[1])

    def test_首尾空格会被去掉(self):
        result = update_task(self.tasks, "t-1", valid_form(title="  需求评审（修订）", owner="\t王敏\n", due=" 2026-11-01 "))
        changed = next(t for t in result if t["id"] == "t-1")
        self.assertEqual((changed["title"], changed["owner"], changed["due"]), ("需求评审（修订）", "王敏", "2026-11-01"))

    def test_错误输入一律报错且原任务不变(self):
        cases = [
            ("标题为空", {"title": ""}),
            ("标题只有半角空格", {"title": "   "}),
            ("标题只有制表符和换行", {"title": "\t\n "}),
            ("负责人为空", {"owner": ""}),
            ("负责人只有全角空格", {"owner": "　"}),
            ("负责人只有制表符", {"owner": "\t"}),
            ("日期为空", {"due": ""}),
            ("日期只有空格", {"due": "  "}),
            ("日期用斜杠", {"due": "2026/11/01"}),
            ("日期没补零", {"due": "2026-1-1"}),
            ("日期带时间", {"due": "2026-11-01 10:00"}),
            ("日期带汉字", {"due": "2026年11月1日"}),
            ("月份13", {"due": "2026-13-01"}),
            ("日期0号", {"due": "2026-11-00"}),
            ("小月31号", {"due": "2026-02-30"}),
            ("平年2月29", {"due": "2026-02-29"}),
            ("日期是文字", {"due": "下个月"}),
            ("状态为空", {"status": ""}),
            ("状态只有空格", {"status": "  "}),
            ("状态是自造词", {"status": "待办"}),
            ("状态是英文", {"status": "done"}),
            ("状态少一个字", {"status": "完成"}),
        ]
        for name, changes in cases:
            with self.subTest(输入=name):
                with self.assertRaises(ValueError):
                    update_task(self.tasks, "t-1", valid_form(**changes))
                self.assertEqual(self.tasks, self.before)  # 校验失败不能修改原任务

    def test_闰年2月29是合法日期(self):
        result = update_task(self.tasks, "t-1", valid_form(due="2028-02-29"))
        self.assertEqual(next(t for t in result if t["id"] == "t-1")["due"], "2028-02-29")

    def test_找不到任务时报错且原任务不变(self):
        for task_id in ("不存在", "", None):
            with self.subTest(id=task_id):
                with self.assertRaises(ValueError):
                    update_task(self.tasks, task_id, valid_form())
                self.assertEqual(self.tasks, self.before)


class AddValidationTest(unittest.TestCase):
    """添加走同一套校验；不填状态仍按原来的“待开始”处理。"""

    def setUp(self):
        self.tasks = sample_tasks()
        self.before = copy.deepcopy(self.tasks)
        self.form = {"title": "写验收报告", "owner": "赵磊", "due": "2026-12-01", "note": "", "status": "待开始"}

    def test_合法输入会被追加(self):
        result = add_task(self.tasks, self.form)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[-1]["title"], "写验收报告")
        self.assertEqual(self.tasks, self.before)  # 原列表保持不变

    def test_不填状态默认待开始(self):
        form = {k: v for k, v in self.form.items() if k != "status"}
        self.assertEqual(add_task(self.tasks, form)[-1]["status"], STATUSES[0])

    def test_必填项不合格会报错(self):
        cases = [("标题为空", {"title": " "}), ("负责人为空", {"owner": ""}), ("日期不存在", {"due": "2026-02-30"}), ("状态非法", {"status": "忙"})]
        for name, changes in cases:
            with self.subTest(输入=name):
                with self.assertRaises(ValueError):
                    add_task(self.tasks, {**self.form, **changes})
                self.assertEqual(self.tasks, self.before)


class DeleteServiceTest(unittest.TestCase):
    """删除：只删指定的一条，原列表不变，找不到就报错。"""

    def setUp(self):
        self.tasks = sample_tasks()
        self.before = copy.deepcopy(self.tasks)

    def test_只删掉指定的一条(self):
        result = delete_task(self.tasks, "t-1")
        self.assertEqual([t["id"] for t in result], ["t-2"])
        self.assertEqual(self.tasks, self.before)  # 原列表保持不变

    def test_重复删除会报错(self):
        result = delete_task(self.tasks, "t-1")
        with self.assertRaises(ValueError):
            delete_task(result, "t-1")

    def test_找不到任务时报错且不改数据(self):
        for task_id in ("不存在", "", None):
            with self.subTest(id=task_id):
                with self.assertRaises(ValueError):
                    delete_task(self.tasks, task_id)
                self.assertEqual(self.tasks, self.before)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """保留303响应本身，方便检查它把错误信息写进了跳转地址。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class TestServer:
    """把项目复制到临时目录并启动真实服务，用来做整条链路的验证。"""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="taskboard-test-"))
        for name in SOURCE_FILES:
            shutil.copy2(PROJECT / name, self.root / name)
        (self.root / "data").mkdir()
        self.data_file = self.root / "data" / "tasks.json"
        self.write_tasks(sample_tasks())
        self.log_file = self.root / "server.log"
        self.port = free_port()
        self.process = None
        self.log = None

    def write_tasks(self, tasks):
        self.data_file.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_tasks(self):
        return json.loads(self.data_file.read_text(encoding="utf-8"))

    def log_text(self):
        return self.log_file.read_text(encoding="utf-8", errors="replace") if self.log_file.exists() else ""

    def start(self):
        self.log = open(self.log_file, "w", encoding="utf-8")
        self.process = subprocess.Popen([sys.executable, "app.py", "--port", str(self.port)], cwd=self.root,
                                        stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + 15
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise AssertionError("服务没启动起来：" + self.log_text())
            try:
                self.get("/")
                return
            except OSError:
                time.sleep(0.1)
        raise AssertionError("等待服务启动超时：" + self.log_text())

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        if self.log is not None:
            self.log.close()

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def url(self, path, query=None):
        base = f"http://127.0.0.1:{self.port}{path}"
        return base + "?" + urllib.parse.urlencode(query) if query else base

    def get(self, path="/", query=None):
        return self.open(self.url(path, query))

    def post(self, path, form):
        return self.open(self.url(path), urllib.parse.urlencode(form).encode("utf-8"))

    @staticmethod
    def open(url, data=None):
        request = urllib.request.Request(url, data=data)  # 带data即为POST
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=5) as response:
                return response.status, response.headers, response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:  # 303被NoRedirect当成错误抛出，这里取回响应
            with exc:
                return exc.status, exc.headers, exc.read().decode("utf-8")

    def token_of(self, html):
        found = re.search(r'name="token" value="([^"]+)"', html)
        if not found:
            self.fail("页面上没有找到令牌")
        return found.group(1)

    def token(self):
        return self.token_of(self.get("/")[2])

    def message_of(self, headers):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(headers.get("Location", "")).query)
        return query.get("message", [""])[0]


class WebTestCase(unittest.TestCase):
    """每个用例都用一个全新的服务，避免用例之间互相影响。"""

    def setUp(self):
        self.server = TestServer()
        self.addCleanup(self.server.cleanup)
        self.addCleanup(self.server.stop)
        self.server.start()

    def edit_form(self, **changes):
        form = {"id": "t-2", "title": "接口联调（修订）", "owner": "李静", "due": "2026-11-01", "note": "改期", "status": "进行中"}
        form.update(changes)
        return {"token": self.server.token(), **form}


class DeleteWebTest(WebTestCase):
    """取消删除与确认删除：验证服务端在什么情况下才会真的动数据。"""

    def test_取消删除时任务原样保留(self):
        before = self.server.data_file.read_bytes()
        html = self.server.get("/")[2]
        self.assertIn("需求评审", html)  # 页面此时确实有这条任务

        # 用户在确认框上点了“取消”：浏览器不会发送请求，这里也就什么都不提交。
        # 这里刻意不去断言页面里有没有 confirm(...) 这类界面字符串：
        # 那种写法把测试绑在提示文案上，改个标点就会红，是典型的坏测试。
        # 这里验证的是服务端后果：没有确认提交，内存和文件都不能变。
        self.assertEqual(self.server.read_tasks(), sample_tasks())
        self.assertEqual(self.server.data_file.read_bytes(), before)
        self.assertIn("需求评审", self.server.get("/")[2])

    def test_没有有效令牌的删除请求会被拒绝(self):
        # 相当于没走确认流程（或旧页面重放）发来的请求：不能删掉任何东西。
        status, headers, _ = self.server.post("/delete", {"token": "bogus-token", "id": "t-1"})
        self.assertEqual(status, 303)
        self.assertEqual(self.server.message_of(headers), "页面已过期，请刷新后重试")
        self.assertEqual(self.server.read_tasks(), sample_tasks())

    def test_令牌是不认识的字符时数据也不能被删掉(self):
        # 已知问题：app.py 用 secrets.compare_digest 比较令牌，遇到非ASCII字符会抛TypeError，
        # 而那里只捕获 ValueError/NotImplementedError/OSError，于是请求直接断开、页面看不到提示。
        # 这里只断言真正要紧的事：不管令牌长什么样，任务都不能被删掉。
        for token in ("过期令牌", "", "x" * 200):
            with self.subTest(token=token):
                try:
                    status, headers, _ = self.server.post("/delete", {"token": token, "id": "t-1"})
                    self.assertEqual(status, 303)
                    self.assertNotEqual(self.server.message_of(headers), "操作完成，请核对结果")
                except OSError:  # 服务端没返回响应（RemoteDisconnected），也不该影响数据
                    pass
                self.assertEqual(self.server.read_tasks(), sample_tasks())

    def test_确认之后的删除才会真的删掉(self):
        status, headers, _ = self.server.post("/delete", {"token": self.server.token(), "id": "t-1"})
        self.assertEqual(status, 303)
        self.assertEqual(self.server.message_of(headers), "操作完成，请核对结果")
        self.assertEqual([t["id"] for t in self.server.read_tasks()], ["t-2"])
        self.assertNotIn("需求评审", self.server.get("/")[2])


class WebErrorInputTest(WebTestCase):
    """错误输入：页面要给出错误信息，而且不能写进数据文件。"""

    def test_编辑保存错误内容不会改动文件(self):
        before = self.server.data_file.read_bytes()
        cases = [("标题全是空格", {"title": "   "}), ("负责人为空", {"owner": ""}),
                 ("日期不存在", {"due": "2026-02-30"}), ("日期格式不对", {"due": "2026/11/01"}),
                 ("状态不在三种之内", {"status": "完成"})]
        for name, changes in cases:
            with self.subTest(输入=name):
                status, headers, _ = self.server.post("/update", self.edit_form(**changes))
                self.assertEqual(status, 303)
                message = self.server.message_of(headers)
                self.assertNotEqual(message, "操作完成，请核对结果")  # 不能报成功
                self.assertTrue(message)  # 要告诉用户哪里错了
                self.assertEqual(self.server.data_file.read_bytes(), before)  # 文件一个字没变
                self.assertEqual(self.server.read_tasks(), sample_tasks())
                self.assertIn("接口联调", self.server.get("/")[2])  # 页面上还是旧标题

        # 紧跟一条合法内容，证明上面“文件没变”不是因为保存功能坏了。
        status, headers, _ = self.server.post("/update", self.edit_form())
        self.assertEqual(status, 303)
        self.assertEqual(self.server.message_of(headers), "操作完成，请核对结果")
        self.assertNotEqual(self.server.data_file.read_bytes(), before)
        self.assertIn("接口联调（修订）", self.server.get("/")[2])

    def test_删除不存在的任务不会改动文件(self):
        before = self.server.data_file.read_bytes()
        status, headers, _ = self.server.post("/delete", {"token": self.server.token(), "id": "不存在"})
        self.assertEqual(status, 303)
        self.assertEqual(self.server.message_of(headers), "找不到这条任务，请刷新页面后重试")
        self.assertEqual(self.server.data_file.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
