# -*- coding: utf-8 -*-
"""t09b 冒烟测试：17 个标准 CRUD Controller。

覆盖要点
1) ``BASE_PATH`` 与 Java ``@RequestMapping`` 完全一致；
2) ``list()`` → ``TableDataInfo``（code=200、msg="查询成功"、rows=服务返回值、total=行数）；
3) ``getInfo(pk)`` → ``AjaxResult``（code=200、data=实体），且主键**原样**传给 service；
4) 有 ``/listAll`` 的类返回**裸列表**（不包 TableDataInfo），且 service 收到的是空实体；
5) 无 ``/listAll`` 的类确实不存在该方法（OdsCxztFwqclls / ZdataTrailTracks）；
6) 三处非模板逻辑：
   - FeeGantryFusion ``list()`` 用 UUID 回填每行 id、``getInfo()`` 直接返回裸实体；
   - vehicleweight ``/map`` 传的是硬编码“逗号串”（不是 list）；
   - vehicleweight ``/{dataSource}`` 把路径段当作 byId 的查询值。

运行：python refactor/_smoke_t09b.py
"""
from __future__ import annotations

import importlib
import inspect
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for _path in (
    ROOT,
    os.path.join(ROOT, "pro-base-common", "src", "main", "java"),
    os.path.join(ROOT, "pro-business-api", "src", "main", "java"),
):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from com.ruoyi.common.constant.HttpStatus import HttpStatus  # noqa: E402
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult  # noqa: E402
from com.ruoyi.common.core.domain.JavaBean import JavaBean  # noqa: E402
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo  # noqa: E402
from com.ruoyi.common.utils.PageUtils import PageUtils  # noqa: E402
from com.ruoyi.common.utils.ServletUtils import (  # noqa: E402
    RequestContextHolder,
    _HttpServletRequest,
    _ServletRequestAttributes,
)

PASS = 0
FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{label} {detail}")
        print(f"  FAIL  {label} {detail}")


def check_eq(label: str, actual, expected) -> None:
    check(label, actual == expected, f"(actual={actual!r}, expected={expected!r})")


# (模块名, BASE_PATH, 主键形参名, 主键样例值, 是否有 /listAll)
CASES = [
    ("DwdLcztFwqjcxxController", "/base/fwqjcxx", "agentPk", "AGENT-PK-1", True),
    ("DwdLcztSfsjcxxController", "/base/sfsjcxx", "agentPk", "AGENT-PK-2", True),
    ("DwdLcztSfzjcxxController", "/base/sfzjcxx", "agentPk", "AGENT-PK-3", True),
    ("OdsCxztFwqcllsController", "/manager/fwqclls", "bigId", 4001, False),
    ("OdsLwzxsfsjFeeStationEnter01Controller", "/base/feeStationEnter", "bigId", 4002, False),
    ("OdsLwzxsfsjFeeStationExit01Controller", "/base/feestationexit", "bigId", "BIG-ID-EXIT", False),
    ("OdsLwzxsfsjFeeGantryFusion01Controller", "/base/feeGantry", "bigId", "BIG-ID-GANTRY", False),
    ("OdsRtSzdnSnapshotFlowProvcaptureAddcodeController", "/base/provcapture", "bigId", 4003, False),
    ("OdsRtSzdnSnapshotFlowStationcaptureAddcodeController", "/base/stationcapture", "bigId", 4004, False),
    ("OdsSzdnGantryController", "/base/gantry", "id", "GANTRY-1", True),
    ("OdsSzdnGantryIpController", "/base/gantryIp", "id", 5001, False),
    ("OdsSzdnProvinceBorderVehicleWeightNewstructureController", "/base/vehicleweight", "dataSource", "DS-001", False),
    ("OdsSzdnSectionController", "/base/section", "id", "SECTION-1", True),
    ("OdsSzdnTollController", "/base/toll", "id", "TOLL-1", True),
    ("OdsSzdnTollStationIpController", "/base/tollStationIp", "id", 5002, False),
    ("OdsYhglVBaseOrgController", "/base/org", "bigId", "ORG-BIG-ID", True),
    ("ZdataTrailTracksController", "/base/trailtracks", "uuid", "UUID-TRACK-1", False),
]

# Java: UUID.randomUUID().toString().replaceAll("-", "") → 32 位无横线小写十六进制
UUID_RE = re.compile(r"^[0-9a-f]{32}$")


class _StubService:
    """按方法名返回伪造数据的 service 替身（不触碰数据库）。"""

    def __init__(self, rows: list) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple]] = []

    def __getattr__(self, name: str):
        def _call(*args, **kwargs):
            self.calls.append((name, args))
            # 列表查询：selectXxxList(...) / selectXxxByQueryUuids(...)
            if "List" in name or "QueryUuids" in name:
                return self.rows
            # byId 查询：返回第一行
            return self.rows[0]

        return _call

    def last_call(self) -> tuple[str, tuple]:
        return self.calls[-1]


def _entity_class(controller_cls) -> type:
    """从 ``list(self, xxx: Xxx)`` 的注解字符串反推实体类。"""
    params = list(inspect.signature(controller_cls.list).parameters.values())
    entity_name = params[1].annotation  # from __future__ import annotations → 字符串
    module = importlib.import_module("com.ruoyi.base.domain." + entity_name)
    return getattr(module, entity_name)


def _install_request_context() -> None:
    """给 startPage() 安装一个假请求上下文。

    【Java→Python】Java 里 startPage() 从 ServletRequest 读 pageNum/pageSize；
    Python 侧由 RequestContextHolder（threading.local）保存当前请求，
    这里模拟 Servlet 容器的入栈动作，否则 getParameter 会抛 AttributeError
    （等价于 Java 在非 Web 线程里调用 startPage 的 NPE）。
    """
    request = _HttpServletRequest(parameters={
        "pageNum": ["2"],
        "pageSize": ["20"],
    })
    RequestContextHolder.setRequestAttributes(_ServletRequestAttributes(request))


def main() -> int:
    check_eq("CASES 数量 = 17 个标准 CRUD Controller", len(CASES), 17)
    _install_request_context()

    for module_name, base_path, pk_name, pk_value, has_list_all in CASES:
        print(f"[{module_name}]")
        module = importlib.import_module("com.ruoyi.base.controller." + module_name)
        controller_cls = getattr(module, module_name)
        check_eq(f"{module_name}.__all__", list(getattr(module, "__all__")), [module_name])

        entity_cls = _entity_class(controller_cls)
        rows = [entity_cls(), entity_cls()]
        stub = _StubService(rows)
        controller = controller_cls(stub)

        # ---- 注入字段名与 Java 一致（camelCase） ---------------------------
        injected = [value for value in vars(controller).values() if value is stub]
        check_eq(f"{module_name} 构造器注入 service", len(injected), 1)

        # ---- 默认构造器走 impl 缺省实现 ------------------------------------
        default_controller = controller_cls()
        default_services = [value for value in vars(default_controller).values()
                            if type(value).__name__.endswith("ServiceImpl")]
        check_eq(f"{module_name} 缺省注入 1 个 service", len(default_services), 1)
        check_eq(
            f"{module_name} 缺省 service 类型",
            type(default_services[0]).__name__,
            module_name.replace("Controller", "ServiceImpl"),
        )

        # ---- 路由前缀 -------------------------------------------------------
        check_eq(f"{module_name}.BASE_PATH", controller_cls.BASE_PATH, base_path)

        # ---- list() ---------------------------------------------------------
        PageUtils.clearPage()
        rsp = controller.list(entity_cls())
        check(f"{module_name}.list 返回 TableDataInfo", isinstance(rsp, TableDataInfo))
        check_eq(f"{module_name}.list.code", rsp.getCode(), HttpStatus.SUCCESS)
        check_eq(f"{module_name}.list.msg", rsp.getMsg(), "查询成功")
        check(f"{module_name}.list.rows 即服务返回值", rsp.getRows() is rows)
        check_eq(f"{module_name}.list.total", rsp.getTotal(), len(rows))
        # startPage() 从假请求读到 pageNum=2 / pageSize=20（Java: TableSupport）
        page_context = PageUtils._context()
        check_eq(f"{module_name}.list 分页上下文 pageNum", page_context.page_num, 2)
        check_eq(f"{module_name}.list 分页上下文 pageSize", page_context.page_size, 20)
        list_method, list_args = stub.calls[-1]
        check(
            f"{module_name}.list 调用 select*List",
            list_method.startswith("select") and list_method.endswith("List"),
            f"(actual={list_method})",
        )
        check_eq(f"{module_name}.list 传入查询实体", type(list_args[0]).__name__, entity_cls.__name__)

        # ---- getInfo(pk) ----------------------------------------------------
        info = controller.getInfo(pk_value)
        info_method, info_args = stub.calls[-1]
        check(
            f"{module_name}.getInfo 调用 select*ById",
            info_method.endswith("ById"),
            f"(actual={info_method})",
        )
        check_eq(f"{module_name}.getInfo 主键原样透传", info_args[0], pk_value)
        check_eq(f"{module_name}.getInfo 主键类型", type(info_args[0]).__name__, type(pk_value).__name__)
        if module_name == "OdsLwzxsfsjFeeGantryFusion01Controller":
            # Java 直接返回实体（不经 AjaxResult），Python 保持一致
            check(f"{module_name}.getInfo 返回裸实体", info is rows[0], f"(actual={type(info).__name__})")
        else:
            check(f"{module_name}.getInfo 返回 AjaxResult", isinstance(info, AjaxResult))
            check_eq(f"{module_name}.getInfo.code", info.get("code"), HttpStatus.SUCCESS)
            check(f"{module_name}.getInfo.data 即实体", info.get("data") is rows[0])

        # ---- listAll --------------------------------------------------------
        if has_list_all:
            all_rows = controller.getListAll()
            check(f"{module_name}.getListAll 返回裸 list", isinstance(all_rows, list))
            check(f"{module_name}.getListAll 不包装 TableDataInfo", not isinstance(all_rows, TableDataInfo))
            check(f"{module_name}.getListAll 元素即服务返回值", all_rows is rows)
            all_method, all_args = stub.calls[-1]
            check_eq(f"{module_name}.getListAll 调用方法", all_method.endswith("List"), True)
            check_eq(
                f"{module_name}.getListAll 传空实体（Java: new Xxx()）",
                type(all_args[0]).__name__,
                entity_cls.__name__,
            )
            empty_entity = all_args[0]
            check(
                f"{module_name}.getListAll 空实体无字段值",
                isinstance(empty_entity, JavaBean)
                and all(getattr(empty_entity, f) is None
                        for f in getattr(empty_entity, "__dataclass_fields__", {})),
            )
        else:
            check(f"{module_name} 无 getListAll", not hasattr(controller, "getListAll"))

    # ---- 非模板逻辑 1：FeeGantryFusion 列表 UUID 回填 ----------------------
    print("[FeeGantryFusion UUID 回填]")
    fee_module = importlib.import_module(
        "com.ruoyi.base.controller.OdsLwzxsfsjFeeGantryFusion01Controller")
    fee_cls = getattr(fee_module, "OdsLwzxsfsjFeeGantryFusion01Controller")
    fee_entity_cls = _entity_class(fee_cls)
    fee_rows = [fee_entity_cls(), fee_entity_cls()]
    check("回填前 id 为 None", all(row.getId() is None for row in fee_rows))
    fee_stub = _StubService(fee_rows)
    fee_cls(fee_stub).list(fee_entity_cls())
    check("回填后 id 均有值", all(row.getId() is not None for row in fee_rows))
    check("回填 id 为 UUID 格式", all(UUID_RE.match(str(row.getId())) for row in fee_rows))
    check("回填 id 互不相同", len({row.getId() for row in fee_rows}) == 2)

    # ---- 非模板逻辑 2：vehicleweight /map 硬编码 uuid 串 -------------------
    print("[vehicleweight /map 硬编码 uuid]")
    weight_module = importlib.import_module(
        "com.ruoyi.base.controller.OdsSzdnProvinceBorderVehicleWeightNewstructureController")
    weight_cls = getattr(weight_module, "OdsSzdnProvinceBorderVehicleWeightNewstructureController")
    weight_rows = [object()]
    weight_stub = _StubService(weight_rows)
    weight_controller = weight_cls(weight_stub)
    mapped = weight_controller.map()
    map_method, map_args = weight_stub.calls[-1]
    check_eq("map 调用 ByQueryUuids", map_method.endswith("ByQueryUuids"), True)
    check_eq("map 传 1 个参数", len(map_args), 1)
    check_eq("map 参数为 str（逗号串）", type(map_args[0]).__name__, "str")
    check_eq("map uuid 串与源码一致", map_args[0], weight_module._MAP_QUERY_UUIDS)
    check_eq("map uuid 串含 2 个 uuid", len(str(map_args[0]).split(",")), 2)
    check("map 返回 AjaxResult", isinstance(mapped, AjaxResult))
    check("map 返回服务数据", mapped.get("data") is weight_rows)

    # ---- 非模板逻辑 3：/{dataSource} 当作 byId 入参 ------------------------
    print("[vehicleweight dataSource 当主键]")
    weight_stub2 = _StubService([object()])
    weight_cls(weight_stub2).getInfo("DS-777")
    ds_method, ds_args = weight_stub2.calls[-1]
    check_eq("dataSource 透传到 ById", (ds_method.endswith("ById"), ds_args), (True, ("DS-777",)))

    RequestContextHolder.resetRequestAttributes()

    print()
    print(f"PASS={PASS} FAIL={FAIL}")
    if FAILURES:
        print("失败明细：")
        for item in FAILURES:
            print("  -", item)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
