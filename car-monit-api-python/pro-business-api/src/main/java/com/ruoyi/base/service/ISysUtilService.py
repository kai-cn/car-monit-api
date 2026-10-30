# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.ISysUtilService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/ISysUtilService.java
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from com.ruoyi.base.domain.CarParaVO import CarParaVO
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.domain.SysUtil import SysUtil
from com.ruoyi.base.domain.TrailBo import TrailBo
from com.ruoyi.base.domain.TrailInfo import TrailInfo
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult

__all__ = ["ISysUtilService"]


class ISysUtilService(ABC):
    """共用类接口表

    【Java→Python】
    1) Java `public interface ISysUtilService` 不继承任何基类（不是 IService），
       Python 用 `class ISysUtilService(ABC)` + `@abstractmethod` 还原。
    2) Java 的 `import com.ruoyi.base.domain.*;` 通配导入 → Python 必须逐个显式 import
       （PEP 8；也是 Python 与 Java 在导入机制上的主要差异之一）。
    3) `Map<K, V>` → `dict[K, V]`；`List<T>` → `list[T]`；`void` → `None`；
       Java 可能返回 null 的实体 → `Optional[...]`（本接口全部返回集合/对象，无 Optional）。
    4) **重点差异**：`Map<ZdataTrailTracks, List<TrailBo>>` 在 Python 中无法直接作为 dict 键——
       `@dataclass` 默认 `eq=True, frozen=False` 时 `__hash__` 被置为 None（不可哈希），
       而 Java 的 Lombok `@Data` 会生成基于字段的 equals/hashCode。
       本接口保留 Java 原类型标注以便对照；实现层（SysUtilServiceImpl）改用
       `dict[int, list[TrailBo]]` 以 `id(entity)` 作键，规避不可哈希问题。
    """

    @abstractmethod
    def saveRedis(self, sysUtil: SysUtil) -> AjaxResult:
        """存数据

        :param sysUtil: 基础类
        :return: 结果

        【Java→Python】抽象方法：实现见 SysUtilServiceImpl（已单独移植到
        python/sys_util_service.py，本重构目录内对应 SysUtilServiceImpl.py）。
        """

    @abstractmethod
    def syncTrack(self, carParaVO: CarParaVO) -> None:
        """同步轨迹

        :param carParaVO: carParaVO 车俩列表
        :return: 结果（Java void → Python None）

        【Java→Python】`void` → `-> None`；方法体中的 `return;` 在 Python 中写 `return None`。
        """

    @abstractmethod
    def changeData(self, tracks: ZdataTrailTracks, josnList: list[TrailBo]) -> TrailInfo:
        """数据转换

        :param tracks: 轨迹实体
        :param josnList: 轨迹点集合（Java List<TrailBo> → list[TrailBo]）
        :return: 结果 TrailInfo

        【Java→Python】Java 方法前的 `public` 修饰符在接口中冗余（接口方法默认 public），
        Python 中一律省略。
        """

    @abstractmethod
    def syncSuspiciousCar(self, carParaVO: CarParaVO) -> dict[ZdataTrailTracks, list[TrailBo]]:
        """同步可疑车俩

        :param carParaVO: 查询条件包
        :return: 轨迹 → 轨迹点列表 的映射

        【Java→Python】返回类型 `Map<ZdataTrailTracks, List<TrailBo>>`：
        Java 用 HashMap（依赖 Lombok 生成的 hashCode/equals）；
        Python 的 `@dataclass` 默认为可变且不可哈希，**不能直接作为 dict 键**。
        实现层改用 `id(entity)` 作为键（详见类注释第 4 点）。
        """

    @abstractmethod
    def syncSuspiciousCarQutaz(self, startNum: int, endNum: int) -> None:
        """同步可疑车俩：定时

        startNum : 起始页面 1  最后页面 10

        :param startNum: 起始页（业务语义，非 SQL OFFSET）
        :param endNum: 结束页
        :return: 无

        【Java→Python】`int` 基本类型 → Python `int`（无 32 位溢出语义，见各实现处的位宽注释）。
        """

    @abstractmethod
    def syncSuspiciousCarQutazNew(self, startNum: int, endNum: int) -> None:
        """同步可疑车俩：定时（新版）

        startNum : 起始页面 1  最后页面 10

        :param startNum: 起始页
        :param endNum: 结束页
        :return: 无

        【Java→Python】与 syncSuspiciousCarQutaz 同签名，区别在实现（并行走廊/游标分页）。
        """

    @abstractmethod
    def carTrackQuery(self, carParaVO: CarParaVO) -> list[TrailInfo]:
        """轨迹查询

        :param carParaVO: 查询条件包（含 carlist / applyTime1 / applyTime2）
        :return: 轨迹信息集合

        【Java→Python】`List<TrailInfo>` → `list[TrailInfo]`；Java 的 Stream
        `carlist.stream().map(CarVO::getCarNo).collect(Collectors.toList())`
        在 Python 中对应列表推导式 `[c.getCarNo() for c in carlist]`。
        """

    @abstractmethod
    def carTrackQueryNew(self, carParaVO: CarParaVO) -> list[ZdataTrailTracks]:
        """轨迹查询（界面查询，直接返回轨迹实体）

        :param carParaVO: 查询条件包
        :return: 轨迹实体集合

        【Java→Python】与 carTrackQuery 的区别：不做 JSON 解析/设备坐标转换，直接返回原始轨迹。
        """

    @abstractmethod
    def getTrailBoList(self, paraTrailPoints: str) -> list[TrailBo]:
        """转josn对象

        :param paraTrailPoints: 轨迹点 JSON 字符串（形如 `[{"captureTime":...}]`）
        :return: 轨迹点对象集合

        【Java→Python】Java 用 Fastjson `JSON.parseArray`；Python 对应 `json.loads`。
        注意原实现对字符串做了清洗（去转义、`ZdTrails:` 前缀等），实现时必须逐字保留。
        """

    @abstractmethod
    def getByTrailBo(self, trailBo: TrailBo) -> TrailBo:
        """获取抓拍对象

        :param trailBo: 轨迹点
        :return: 补全设备信息后的轨迹点

        【Java→Python】Java 返回 null 表示未匹配到设备；Python 返回 None。
        """

    @abstractmethod
    def syncSnapshotFlow(self, snapshotFlow: OdsRtSzdnSnapshotFlowAddcode) -> None:
        """获取门架抓拍流水

        :param snapshotFlow: 查询条件（含 startNum/endNum 分页与时间范围）
        :return: 无

        【Java→Python】该方法内部依赖 Redis 缓存与批量入库，Python 侧沿用 RedisCache 替身。
        """

    @abstractmethod
    def syncFeeRecords(self, feeRecords: OdsLwzxsfsjFeeRecords01) -> None:
        """获取门架交易流水

        :param feeRecords: 查询条件（含 startNum/endNum 分页与时间范围）
        :return: 无

        【Java→Python】与 syncSnapshotFlow 对称：分页拉取 → 组装 → 写 Redis。
        """

    @abstractmethod
    def separateSnapshotFlowTimeList(self) -> None:
        """门架抓拍流水 和 获取门架交易流水 对比

        :return: 无

        【Java→Python】无参方法；实现依赖类内缓存（Redis）而非入参，注意线程安全差异。
        """

    @abstractmethod
    def syncSuspiciousCarDB(self) -> None:
        """根据 轨迹点和门架流水 找到可疑车辆 并放到redis中

        :return: 无

        【Java→Python】定时任务入口；Python 侧由 task 模块的调度器调用。
        """
