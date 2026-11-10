"""筛选功能的测试与演示。

运行方式（Windows，在本项目文件夹打开终端）：
    py test_filter.py            # 跑测试
    py test_filter.py --demo     # 打印12条数据的预期结果表
    py -m unittest test_filter -v
macOS/Linux 把 py 换成 python3。

规则：负责人和状态按完整值匹配；关键词在 title 或 note 中匹配、忽略首尾空格；
多个条件同时满足（是“并且”不是“或者”）；查询不删除、不修改原数据，结果保留 id。

下方 QUERIES 是对照表，测试和 --demo 共用同一份数据，
所以“演示里写的预期”和“测试断言的结果”不可能对不上。
"""
import copy
import sys
import unittest

from service import filter_tasks, update_task


def demo_tasks():
    """12 条演示数据（要求至少10条），覆盖多个负责人、三种状态、关键词命中标题和说明两种情况。"""
    return [
        {"id": "id-01", "title": "需求评审", "owner": "张明", "due": "2026-09-30", "note": "第一次评审", "status": "已完成"},
        {"id": "id-02", "title": "接口联调", "owner": "张明", "due": "2026-10-15", "note": "和李静一起", "status": "进行中"},
        {"id": "id-03", "title": "接口文档", "owner": "李静", "due": "2026-10-20", "note": "补齐字段说明", "status": "待开始"},
        {"id": "id-04", "title": "数据保存", "owner": "李静", "due": "2026-10-25", "note": "JSON落盘", "status": "已完成"},
        {"id": "id-05", "title": "界面排版", "owner": "王敏", "due": "2026-11-01", "note": "移动端也要能用", "status": "进行中"},
        {"id": "id-06", "title": "筛选功能", "owner": "王敏", "due": "2026-11-05", "note": "按负责人和状态查", "status": "待开始"},
        {"id": "id-07", "title": "进度统计", "owner": "赵磊", "due": "2026-11-10", "note": "完成率计算", "status": "待开始"},
        {"id": "id-08", "title": "验收演示", "owner": "赵磊", "due": "2026-11-15", "note": "准备接口演示", "status": "已完成"},
        {"id": "id-09", "title": "备份数据", "owner": "陈曦", "due": "2026-11-20", "note": "每周备份一次", "status": "进行中"},
        {"id": "id-10", "title": "写验收报告", "owner": "陈曦", "due": "2026-11-25", "note": "含截图", "status": "待开始"},
        {"id": "id-11", "title": "周会纪要", "owner": "张明", "due": "2026-11-30", "note": "记录待办", "status": "进行中"},
        {"id": "id-12", "title": "整理需求清单", "owner": "李静", "due": "2026-12-05", "note": "接口和界面分开列", "status": "待开始"},
    ]


ALL = [t["id"] for t in demo_tasks()]

# （说明，传给 filter_tasks 的条件，按原始顺序期望命中的 id）
QUERIES = [
    ("不加任何条件", {}, ALL),
    ("owner=张明：完整值匹配", {"owner": "张明"}, ["id-01", "id-02", "id-11"]),
    ("status=进行中：完整值匹配", {"status": "进行中"}, ["id-02", "id-05", "id-09", "id-11"]),
    ("owner=张明 且 status=进行中：两个条件同时满足", {"owner": "张明", "status": "进行中"}, ["id-02", "id-11"]),
    ("keyword=接口：标题命中 id-02、id-03，说明命中 id-08、id-12", {"keyword": "接口"}, ["id-02", "id-03", "id-08", "id-12"]),
    ("keyword=接口：首尾各加空格，结果同上", {"keyword": "  接口  "}, ["id-02", "id-03", "id-08", "id-12"]),
    ("owner=李静 且 keyword=接口", {"owner": "李静", "keyword": "接口"}, ["id-03", "id-12"]),
    ("owner=李静 且 status=待开始 且 keyword=文档", {"owner": "李静", "status": "待开始", "keyword": "文档"}, ["id-03"]),
    ("owner=张：只写一半，完整值匹配查不到", {"owner": "张"}, []),
    ("status=进行：只写一半，完整值匹配查不到", {"status": "进行"}, []),
    ("keyword=JSON：说明里的英文也能命中", {"keyword": "JSON"}, ["id-04"]),
    ("owner=王敏 且 status=已完成 且 keyword=接口：条件互相冲突", {"owner": "王敏", "status": "已完成", "keyword": "接口"}, []),
]


def hit_ids(tasks, conditions):
    return [t["id"] for t in filter_tasks(tasks, **conditions)]


def describe(conditions):
    return " 且 ".join(f"{key}={value!r}" for key, value in conditions.items()) if conditions else "（无）"


def titles(tasks, ids):
    if not ids:
        return "（没有命中）"
    by_id = {t["id"]: t["title"] for t in tasks}
    return "、".join(f"{i} {by_id[i]}" for i in ids)


class FilterTest(unittest.TestCase):
    """按对照表逐条验证筛选结果。"""

    def setUp(self):
        self.tasks = demo_tasks()
        self.before = copy.deepcopy(self.tasks)

    def test_对照表的每条预期都成立(self):
        for label, conditions, expected in QUERIES:
            with self.subTest(查询=label):
                self.assertEqual(hit_ids(self.tasks, conditions), expected)

    def test_演示数据至少10条且id不重复(self):
        self.assertGreaterEqual(len(self.tasks), 10)
        self.assertEqual(len(set(ALL)), len(ALL))

    def test_不带条件时返回全部且是新列表(self):
        result = filter_tasks(self.tasks)
        self.assertEqual([t["id"] for t in result], ALL)
        self.assertIsNot(result, self.tasks)  # 是副本，不是原列表

    def test_空数据返回空(self):
        self.assertEqual(filter_tasks([], owner="张明", status="进行中", keyword="接口"), [])

    def test_条件参数留空表示这一项不筛(self):
        self.assertEqual(hit_ids(self.tasks, {"owner": "", "status": "", "keyword": ""}), ALL)
        self.assertEqual(hit_ids(self.tasks, {"keyword": "   "}), ALL)  # 只有空格等于没填

    def test_查询不删除也不修改原数据(self):
        for label, conditions, _ in QUERIES:
            with self.subTest(查询=label):
                filter_tasks(self.tasks, **conditions)
                self.assertEqual(self.tasks, self.before)  # 原数据完好

    def test_改动筛选结果不会影响原数据(self):
        result = filter_tasks(self.tasks, owner="张明")
        result[0]["title"] = "被改坏了"
        result[0]["owner"] = "被改坏了"
        result[0]["status"] = "被改坏了"
        del result[0]  # 删掉筛选结果里的一条
        result.append({"id": "id-99", "title": "凭空多出来的"})
        self.assertEqual(self.tasks, self.before)
        self.assertEqual(len(self.tasks), 12)

    def test_筛选结果保留id并能直接拿去编辑(self):
        picked = filter_tasks(self.tasks, owner="张明", status="进行中")
        self.assertEqual([t["id"] for t in picked], ["id-02", "id-11"])
        self.assertEqual(picked[0]["id"], "id-02")
        form = {"title": "接口联调（改期）", "owner": "张明", "due": "2026-12-31", "note": "和李静一起", "status": "已完成"}
        updated = update_task(picked, "id-02", form)  # 用筛选结果里的 id 编辑
        self.assertEqual(next(t for t in updated if t["id"] == "id-02")["status"], "已完成")
        self.assertEqual(self.tasks, self.before)  # 原数据仍未被改动


class FilterWebTest(unittest.TestCase):
    """界面上按条件查询也要走通（web.py 是位置传参，这里顺便确认参数顺序没错）。"""

    def setUp(self):
        from test_edit import TestServer  # 复用“临时目录+真服务”测试工具
        self.server = TestServer()
        self.server.write_tasks(demo_tasks())
        self.addCleanup(self.server.cleanup)
        self.addCleanup(self.server.stop)
        self.server.start()

    def test_按负责人和状态查询(self):
        html = self.server.get("/", query={"owner": "张明", "status": "进行中"})[2]
        self.assertIn("接口联调", html)
        self.assertIn("周会纪要", html)
        self.assertNotIn("需求评审", html)  # 张明 但已完成
        self.assertNotIn("界面排版", html)  # 进行中 但王敏

    def test_按关键词查询且忽略首尾空格(self):
        html = self.server.get("/", query={"keyword": "  接口  "})[2]
        self.assertIn("接口联调", html)
        self.assertIn("接口文档", html)
        self.assertIn("验收演示", html)
        self.assertIn("整理需求清单", html)
        self.assertNotIn("需求评审", html)

    def test_查询后数据文件没有被改写(self):
        before = self.server.data_file.read_bytes()
        self.server.get("/", query={"owner": "李静", "keyword": "接口"})
        self.assertEqual(self.server.data_file.read_bytes(), before)
        self.assertEqual(self.server.read_tasks(), demo_tasks())


def show():
    """打印12条数据下每条查询的预期结果和实际结果。"""
    tasks = demo_tasks()
    print(f"筛选演示：{len(tasks)} 条数据")
    for t in tasks:
        print(f"  {t['id']}  {t['title']}｜{t['owner']}｜{t['status']}｜说明：{t['note']}")
    print()
    for number, (label, conditions, expected) in enumerate(QUERIES, 1):
        actual = hit_ids(tasks, conditions)
        same = "与预期一致" if actual == expected else "！！与预期不一致"
        print(f"{number:>2}. {label}")
        print(f"    条件：{describe(conditions)}")
        print(f"    预期 {len(expected):>2} 条：{titles(tasks, expected)}")
        print(f"    实际 {len(actual):>2} 条：{titles(tasks, actual)}   [{same}]")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        show()
    else:
        unittest.main(verbosity=2)
