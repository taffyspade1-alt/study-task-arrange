"""进度统计的测试。

运行方式（Windows，在本项目文件夹打开终端）：
    py test_stats.py
    py -m unittest test_stats -v

统计口径固定为全部任务：已完成只数“已完成”，未完成=总数-已完成，
完成率按百分比保留1位小数，总数为0时返回0。筛选只改变下方列表，
不影响顶部统计。
"""
import copy
import re
import unittest

from service import statistics
from test_edit import TestServer


def fixture_tasks():
    """本次统一测试数据：10条，待开始4条、进行中3条、已完成3条。"""
    return [
        {"id": "1", "title": "整理需求清单", "owner": "张明", "due": "2026-10-10", "note": "示例任务", "status": "待开始"},
        {"id": "2", "title": "制作页面原型", "owner": "李静", "due": "2026-10-11", "note": "示例任务", "status": "进行中"},
        {"id": "3", "title": "测试添加功能", "owner": "张明", "due": "2026-10-12", "note": "示例任务", "status": "已完成"},
        {"id": "4", "title": "编写说明", "owner": "王敏", "due": "2026-10-13", "note": "示例任务", "status": "待开始"},
        {"id": "5", "title": "完善状态更新", "owner": "赵磊", "due": "2026-10-14", "note": "示例任务", "status": "已完成"},
        {"id": "6", "title": "准备演示数据", "owner": "张明", "due": "2026-10-15", "note": "示例任务", "status": "进行中"},
        {"id": "7", "title": "修复日期问题", "owner": "陈曦", "due": "2026-10-16", "note": "示例任务", "status": "待开始"},
        {"id": "8", "title": "核对保存结果", "owner": "李静", "due": "2026-10-17", "note": "示例任务", "status": "已完成"},
        {"id": "9", "title": "测试筛选功能", "owner": "张明", "due": "2026-10-18", "note": "示例任务", "status": "进行中"},
        {"id": "10", "title": "整理交付文件", "owner": "王敏", "due": "2026-10-19", "note": "示例任务", "status": "待开始"},
    ]


STATS_PATTERN = re.compile(r"全部任务 (\d+)　已完成 (\d+)　未完成 (\d+)　完成率 ([\d.]+)%")


def stats_of(html):
    """从页面顶部取出四个统计值。"""
    found = STATS_PATTERN.search(html)
    if not found:
        raise AssertionError("页面上没有找到进度统计：" + html[:300])
    total, completed, remaining, percent = found.groups()
    return int(total), int(completed), int(remaining), float(percent)


def make_tasks(*statuses):
    return [{"id": str(i), "title": f"任务{i}", "owner": "张明", "due": "2026-12-31", "note": "", "status": s}
            for i, s in enumerate(statuses, 1)]


class StatisticsUnitTest(unittest.TestCase):
    """统计函数的边界与口径。"""

    def test_统一十条数据的基线(self):
        self.assertEqual(statistics(fixture_tasks()),
                         {"total": 10, "completed": 3, "remaining": 7, "percent": 30.0})

    def test_只把已完成计入完成数(self):
        tasks = make_tasks("已完成", "进行中", "待开始", "")
        self.assertEqual(statistics(tasks),
                         {"total": 4, "completed": 1, "remaining": 3, "percent": 25.0})

    def test_空列表四项都是零(self):
        self.assertEqual(statistics([]),
                         {"total": 0, "completed": 0, "remaining": 0, "percent": 0})

    def test_单条任务的三种状态(self):
        self.assertEqual(statistics(make_tasks("待开始")),
                         {"total": 1, "completed": 0, "remaining": 1, "percent": 0.0})
        self.assertEqual(statistics(make_tasks("进行中")),
                         {"total": 1, "completed": 0, "remaining": 1, "percent": 0.0})
        self.assertEqual(statistics(make_tasks("已完成")),
                         {"total": 1, "completed": 1, "remaining": 0, "percent": 100.0})

    def test_完成率保留一位小数(self):
        cases = [
            (make_tasks("已完成", "待开始", "待开始"), 33.3),
            (make_tasks("已完成", "已完成", "待开始"), 66.7),
            (make_tasks("已完成", "待开始", "待开始", "待开始", "待开始", "待开始"), 16.7),
            (make_tasks(*(["已完成"] * 3 + ["待开始"] * 8)), 27.3),
        ]
        for tasks, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(statistics(tasks)["percent"], expected)

    def test_统计不修改原列表(self):
        tasks = fixture_tasks()
        before = copy.deepcopy(tasks)
        statistics(tasks)
        self.assertEqual(tasks, before)


class StatisticsWebTest(unittest.TestCase):
    """真实服务上的统计：默认、筛选、改状态、新增。"""

    def setUp(self):
        self.server = TestServer()
        self.server.write_tasks(fixture_tasks())
        self.addCleanup(self.server.cleanup)
        self.addCleanup(self.server.stop)
        self.server.start()

    def test_顶部显示10条中3条完成(self):
        html = self.server.get("/")[2]
        self.assertEqual(stats_of(html), (10, 3, 7, 30.0))
        self.assertNotIn("0.3%", html)
        self.assertNotIn("3000%", html)

    def test_筛选后列表变4条但统计不变(self):
        html = self.server.get("/", query={"owner": "张明"})[2]
        self.assertEqual(stats_of(html), (10, 3, 7, 30.0))
        self.assertEqual(html.count("编辑 / 状态"), 4)
        for title in ("整理需求清单", "测试添加功能", "准备演示数据", "测试筛选功能"):
            self.assertIn(title, html)
        self.assertNotIn("制作页面原型", html)

    def test_改状态后统计变为四个完成(self):
        task = next(t for t in self.server.read_tasks() if t["status"] == "待开始")
        form = {"token": self.server.token(), "id": task["id"], "title": task["title"],
                "owner": task["owner"], "due": task["due"], "note": task["note"], "status": "已完成"}
        status, headers, _ = self.server.post("/update", form)
        self.assertEqual(status, 303)
        self.assertEqual(self.server.message_of(headers), "操作完成，请核对结果")
        self.assertEqual(stats_of(self.server.get("/")[2]), (10, 4, 6, 40.0))

    def test_重启后统计仍然正确(self):
        task = next(t for t in self.server.read_tasks() if t["status"] == "待开始")
        form = {"token": self.server.token(), "id": task["id"], "title": task["title"],
                "owner": task["owner"], "due": task["due"], "note": task["note"], "status": "已完成"}
        self.server.post("/update", form)
        self.server.stop()
        self.server.start()
        self.assertEqual(stats_of(self.server.get("/")[2]), (10, 4, 6, 40.0))

    def test_改状态再新增后统计变为十一条(self):
        # 按任务步骤5的顺序：先把一条待开始改成已完成（10、4、6、40%），
        # 再添加一条待开始（11、4、7、36.4%）。
        task = next(t for t in self.server.read_tasks() if t["status"] == "待开始")
        update = {"token": self.server.token(), "id": task["id"], "title": task["title"],
                  "owner": task["owner"], "due": task["due"], "note": task["note"], "status": "已完成"}
        self.server.post("/update", update)
        form = {"token": self.server.token(), "title": "统计验证新增任务", "owner": "周涛",
                "due": "2026-12-31", "note": "", "status": "待开始"}
        status, headers, _ = self.server.post("/add", form)
        self.assertEqual(status, 303)
        self.assertEqual(self.server.message_of(headers), "操作完成，请核对结果")
        self.assertEqual(stats_of(self.server.get("/")[2]), (11, 4, 7, 36.4))


class EmptyStatisticsWebTest(unittest.TestCase):
    """空数据与单条任务的边界，走真实服务。"""

    def setUp(self):
        self.server = TestServer()
        self.server.write_tasks([])
        self.addCleanup(self.server.cleanup)
        self.addCleanup(self.server.stop)
        self.server.start()

    def test_空列表显示四项零且不报错(self):
        html = self.server.get("/")[2]
        self.assertEqual(stats_of(html), (0, 0, 0, 0))
        self.assertIn("暂无匹配任务", html)

    def test_添加一条待开始后为1_0_1_0(self):
        form = {"token": self.server.token(), "title": "唯一任务", "owner": "张明",
                "due": "2026-12-31", "note": "", "status": "待开始"}
        self.server.post("/add", form)
        self.assertEqual(stats_of(self.server.get("/")[2]), (1, 0, 1, 0.0))

    def test_唯一任务改为已完成后为1_1_0_100(self):
        form = {"token": self.server.token(), "title": "唯一任务", "owner": "张明",
                "due": "2026-12-31", "note": "", "status": "待开始"}
        self.server.post("/add", form)
        task = self.server.read_tasks()[0]
        update = {"token": self.server.token(), "id": task["id"], "title": task["title"],
                  "owner": task["owner"], "due": task["due"], "note": task["note"], "status": "已完成"}
        self.server.post("/update", update)
        self.assertEqual(stats_of(self.server.get("/")[2]), (1, 1, 0, 100.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
