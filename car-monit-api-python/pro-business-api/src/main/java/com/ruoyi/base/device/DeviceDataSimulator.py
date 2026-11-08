# -*- coding: utf-8 -*-
"""com.ruoyi.base.device.DeviceDataSimulator

源文件：pro-business-api/src/main/java/com/ruoyi/base/device/DeviceDataSimulator.java

硬件设备数据上报模拟器

功能说明：
1. 模拟门架抓拍、省界称重、收费站、服务区等设备
2. 生成模拟数据并上报到Kafka
3. 支持批量上报、延迟模拟等

【Java→Python 本文件重点差异】
1) `@Slf4j` → `log = logging.getLogger(__name__)`；`@Component` → **无注解**，
   Spring 容器不参与，改由构造器注入（详见第 2 条）。
2) `@Autowired private KafkaTemplate<String, Object> kafkaTemplate` →
   构造器可选参数 + 缺省 `defaultKafkaTemplate()`（与 KafkaProducerService 一致），
   这样脱离 Spring 也能直接 new 出来做测试。
3) `java.util.Date` → `datetime`（全工程统一约定）：
     - `new Date()`            → `datetime.now()`
     - `date.getTime()`        → `int(date.timestamp() * 1000)`（`_epochMillis`）
     - `new Date(long millis)` → `datetime.fromtimestamp(millis / 1000.0)`
   **注意**：Java 的 Date 是“绝对时间 + 时区格式化”，Python 的 naive datetime
   直接表示本地时间，两者在默认时区下等价（`_epochMillis` 的模块注释已说明）。
4) `private static class DeviceInfo` + `@AllArgsConstructor @Data` →
   模块级 `@dataclass DeviceInfo`。字段名**保持 camelCase**（deviceId/deviceType/...），
   因为 Java 源码是**直接字段访问**（`device.deviceType`）而不是 getter，
   Python 侧同样用 `device.deviceType` 才能逐字对齐。
5) `switch (device.deviceType) { case "GANTRY": ... default: ... }` →
   `if/elif/else`。Java 的 switch 没有 case 穿透（每个分支都 return），
   因此 if/elif 与之一一对应；`default` 落到最后一个 `else`。
6) `ThreadLocalRandom.current()` → `java.util.concurrent.ThreadLocalRandom` 替身；
   `nextInt(origin, bound)` 在 Java 是**左闭右开**，替身已还原该语义。
7) `Thread.sleep(ms)` → `time.sleep(ms / 1000.0)`；`InterruptedException` →
   Python 的 `InterruptedError`（详见 simulateBatchReport 内注释）。
8) `new BigDecimal(device.lon)` → `Decimal(str(device.lon))`：实体字段
   `OdsRtSzdnSnapshotFlowAddcode.lon/lat` 已映射为 `decimal.Decimal`，直接按
   字符串构造可保住十进制精度（复核高危②：此前 float 会丢精度）。
9) **原工程缺陷（忠实保留）**：`reportToKafka` 里
   `String jsonData = JSON.toJSONString(data);` 计算后**从未使用**
   （真正 send 的是 data 对象本身）。按“一比一”要求保留该行并标注。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from com.alibaba.fastjson2.JSON import JSON
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import (
    OdsRtSzdnSnapshotFlowAddcode,
)
from java.lang.System import System
from java.lang.Thread import InterruptedException, Thread
from java.text.SimpleDateFormat import SimpleDateFormat
from java.util.UUID import UUID
from java.util.concurrent.ThreadLocalRandom import ThreadLocalRandom
from org.springframework.kafka.core.KafkaTemplate import (
    KafkaTemplate,
    defaultKafkaTemplate,
)

__all__ = ["DeviceDataSimulator", "DeviceInfo"]

log = logging.getLogger(__name__)


def _epochMillis(value: datetime) -> int:
    """等价 `Date#getTime()`（epoch 毫秒）。

    【Java→Python】naive `datetime.timestamp()` 按本地时区换算，
    与 Java `Date.getTime()`（UTC 基准毫秒）结果一致。
    """
    return int(value.timestamp() * 1000)


@dataclass
class DeviceInfo:
    """设备信息（对应 Java 的 `private static class DeviceInfo`）。

    【Java→Python】`@lombok.AllArgsConstructor` → dataclass 的字段顺序即
    构造器参数顺序（deviceId, deviceType, roadName, district, lon, lat）；
    `@lombok.Data` 的 getter/setter 本类源码未使用（直接字段访问），故不继承 JavaBean。
    """

    deviceId: str
    deviceType: str
    roadName: str
    district: str
    lon: float
    lat: float


class DeviceDataSimulator(object):
    """硬件设备数据上报模拟器（`@Component`）。"""

    KAFKA_TOPIC_RAW_DATA = "device-raw-data"

    # 模拟设备列表（Java: `private static final List<DeviceInfo> DEVICES = Arrays.asList(...)`）
    DEVICES: List[DeviceInfo] = [
        DeviceInfo("Gantry-001", "GANTRY", "京承高速", "朝阳区", 116.404, 39.915),
        DeviceInfo("Gantry-002", "GANTRY", "京承高速", "顺义区", 116.653, 40.134),
        DeviceInfo("Border-001", "BORDER_WEIGHING", "京冀界", "大兴区", 116.302, 39.732),
        DeviceInfo("Station-001", "TOLL_STATION", "望京站", "朝阳区", 116.473, 39.983),
        DeviceInfo("Station-002", "TOLL_STATION", "顺义站", "顺义区", 116.682, 40.137),
        DeviceInfo("Service-001", "SERVICE_AREA", "顺义服务区", "顺义区", 116.632, 40.083),
    ]

    # 模拟车牌号（Java: `Arrays.asList("京A", ..., "京L")`）
    PLATE_PREFIX: List[str] = [
        "京A", "京B", "京C", "京E", "京F", "京G", "京H", "京J", "京K", "京L",
    ]

    def __init__(self,
                 kafkaTemplate: Optional[KafkaTemplate] = None) -> None:
        # 注入KafkaTemplate（Java: @Autowired；缺省取进程级单例替身）
        self.kafkaTemplate: KafkaTemplate = kafkaTemplate or defaultKafkaTemplate()
        # 随机数生成器（Java: `private final ThreadLocalRandom random = ThreadLocalRandom.current();`）
        self.random = ThreadLocalRandom.current()

    # ==================== 对外方法 ====================

    def simulateSingleReport(self) -> None:
        """单条设备数据上报。"""
        # 随机选择一个设备（Java: DEVICES.get(random.nextInt(DEVICES.size())))
        device: DeviceInfo = self.DEVICES[self.random.nextInt(len(self.DEVICES))]

        # 生成数据（Java: Object data = generateDeviceData(device)）
        data: Any = self.generateDeviceData(device)

        # 上报Kafka
        self.reportToKafka(device, data)

    def simulateBatchReport(self, count: int) -> None:
        """批量设备数据上报。

        :param count: 上报条数
        """
        log.info("[设备模拟] 开始批量上报：count=%s", count)

        for i in range(count):
            self.simulateSingleReport()

            # 随机延迟0-100ms
            try:
                # 【Java→Python】Thread.sleep(long millis) → time.sleep(秒)
                Thread.sleep(self.random.nextInt(100))
            except InterruptedException:
                # Java: Thread.currentThread().interrupt();
                # 【Java→Python】Python 线程没有“中断标志位”这一概念，
                # Thread.currentThread().interrupt() 只能记录一个标志（替身已实现），
                # 但标准 time.sleep 不会被中断，因此该分支实际不会触发；
                # 保留结构以对齐 Java 的异常处理（见 java.lang.Thread 替身说明）。
                Thread.currentThread().interrupt()

        log.info("[设备模拟] 批量上报完成")

    # ==================== 数据生成 ====================

    def generateDeviceData(self, device: DeviceInfo) -> Any:
        """根据设备类型生成对应数据。"""
        # 【Java→Python】switch(String) → if/elif；每个 case 都 return，无穿透
        if device.deviceType == "GANTRY":
            return self.generateGantryData(device)
        elif device.deviceType == "BORDER_WEIGHING":
            return self.generateBorderWeighingData(device)
        elif device.deviceType == "TOLL_STATION":
            return self.generateTollStationData(device)
        elif device.deviceType == "SERVICE_AREA":
            return self.generateServiceAreaData(device)
        else:
            return self.generateGantryData(device)

    def generateGantryData(self, device: DeviceInfo) -> OdsRtSzdnSnapshotFlowAddcode:
        """生成门架抓拍数据。

        与项目中OdsRtSzdnSnapshotFlowAddcode表结构对应
        """
        data: OdsRtSzdnSnapshotFlowAddcode = OdsRtSzdnSnapshotFlowAddcode()

        # 基础信息
        data.setBigId(UUID.randomUUID().toString().replace("-", ""))
        data.setDatasource("SIMULATED_GANTRY")
        data.setCameratype("HIGH_SPEED_CAMERA")
        data.setDeviceid(device.deviceId)

        # 门架信息
        data.setGantrycode(device.deviceId)
        data.setGantryname(device.roadName)
        data.setRoadcode("G101")
        data.setRoadname(device.roadName)
        data.setSectioncode("SEC-001")
        data.setSectionname(device.district + "段")

        # 经纬度
        # 【Java→Python】Java 是 `new BigDecimal(device.lon)`；实体字段 lon/lat
        # 为 decimal.Decimal，故按字符串构造 Decimal（复核高危②，不再经过 float）。
        data.setLon(Decimal(str(device.lon)))
        data.setLat(Decimal(str(device.lat)))

        # 车辆信息
        plateNumber: str = self.generatePlateNumber()
        data.setPlatenumber(plateNumber)
        data.setPlatecolor(self.randomPlateColor())
        data.setPlatetypecode(1 if self.random.nextBoolean() else 2)
        data.setCartype(self.randomVehicleType())
        data.setCartypecode(self.random.nextInt(1, 10))

        # 时间信息
        captureTime: datetime = datetime.now()  # Java: Date captureTime = new Date();
        data.setSnapshottime(captureTime)
        data.setSnapshottimeunix(_epochMillis(captureTime))
        # Java: new Date(captureTime.getTime() + random.nextInt(100, 500))
        data.setReceivedtime(datetime.fromtimestamp(
            (_epochMillis(captureTime) + self.random.nextInt(100, 500)) / 1000.0))
        data.setLoadtime(datetime.now())

        # 图片信息
        imagePath: str = ("/images/" + self.formatDate(captureTime) + "/"
                          + data.getBigId() + ".jpg")
        data.setSnappicturepath(imagePath)

        # 速度信息 (speed字段不存在, 已移除)

        return data

    def generateBorderWeighingData(self, device: DeviceInfo) -> Dict[str, Any]:
        """生成省界称重数据。"""
        # 【Java→Python】`new HashMap<>()` → `{}`（Python 内置 dict 即哈希表，插入有序）
        data: Dict[str, Any] = {}

        data["bigId"] = UUID.randomUUID().toString().replace("-", "")
        data["deviceId"] = device.deviceId
        data["deviceType"] = "BORDER_WEIGHING"
        data["plateNumber"] = self.generatePlateNumber()
        data["captureTime"] = datetime.now()
        data["vehicleWeight"] = self.random.nextDouble(1.0, 49.0)
        data["axleCount"] = self.random.nextInt(2, 7)
        data["overweight"] = self.random.nextBoolean()
        data["lon"] = device.lon
        data["lat"] = device.lat
        data["location"] = device.roadName

        return data

    def generateTollStationData(self, device: DeviceInfo) -> Dict[str, Any]:
        """生成收费站数据。"""
        data: Dict[str, Any] = {}

        data["bigId"] = UUID.randomUUID().toString().replace("-", "")
        data["deviceId"] = device.deviceId
        data["deviceType"] = "TOLL_STATION"
        data["plateNumber"] = self.generatePlateNumber()
        data["captureTime"] = datetime.now()
        data["direction"] = "IN" if self.random.nextBoolean() else "OUT"
        data["laneId"] = "LANE-" + str(self.random.nextInt(1, 6))
        data["tollFee"] = self.random.nextDouble(5.0, 500.0)
        data["lon"] = device.lon
        data["lat"] = device.lat
        data["location"] = device.roadName

        return data

    def generateServiceAreaData(self, device: DeviceInfo) -> Dict[str, Any]:
        """生成服务区数据。"""
        data: Dict[str, Any] = {}

        data["bigId"] = UUID.randomUUID().toString().replace("-", "")
        data["deviceId"] = device.deviceId
        data["deviceType"] = "SERVICE_AREA"
        data["plateNumber"] = self.generatePlateNumber()
        data["captureTime"] = datetime.now()
        # Java: Arrays.asList("ENTER", "EXIT", "PARKING").get(random.nextInt(3))
        # 【Java→Python】`Arrays.asList(...)` → list 字面量（不可变语义用 tuple 更接近，
        # 但源码只读不写，两者等价，这里用 list 保持下标访问写法一致）
        actions: List[str] = ["ENTER", "EXIT", "PARKING"]
        data["action"] = actions[self.random.nextInt(3)]
        data["lon"] = device.lon
        data["lat"] = device.lat
        data["location"] = device.roadName

        return data

    # ==================== 上报 ====================

    def reportToKafka(self, device: DeviceInfo, data: Any) -> None:
        """上报数据到Kafka。"""
        # 【Java→Python】字符串 + long → 必须显式 str()（Python 不允许 str + int）
        key: str = device.deviceId + ":" + str(System.currentTimeMillis())
        # 【Java→Python】**原工程缺陷，忠实保留**：这里算出 jsonData 后从未使用
        # （下一行 send 传的是 data 对象，由 KafkaTemplate 的序列化器负责转 JSON）。
        # 因此该行对运行结果没有任何影响；如按“修正缺陷”的方式删掉，
        # 反而不是一比一重构。`# noqa: F841` 仅用于抑制未使用变量告警。
        jsonData: str = JSON.toJSONString(data)  # noqa: F841 - 原工程未使用（见上）

        log.debug("[设备上报] 类型=%s, 设备=%s, key=%s",
                  device.deviceType, device.deviceId, key)

        self.kafkaTemplate.send(self.KAFKA_TOPIC_RAW_DATA, key, data)

    # ==================== 工具方法 ====================

    def generatePlateNumber(self) -> str:
        """生成车牌号。"""
        prefix: str = self.PLATE_PREFIX[self.random.nextInt(len(self.PLATE_PREFIX))]
        # Java: String.valueOf(random.nextInt(10000, 99999))
        suffix: str = str(self.random.nextInt(10000, 99999))
        return prefix + suffix

    def randomPlateColor(self) -> str:
        """随机车牌颜色。"""
        colors: List[str] = ["蓝", "黄", "绿", "白", "黑"]
        return colors[self.random.nextInt(len(colors))]

    def randomVehicleType(self) -> str:
        """随机车辆类型。"""
        types: List[str] = ["小型轿车", "大型客车", "货车", "危险品运输车"]
        return types[self.random.nextInt(len(types))]

    def formatDate(self, date: datetime) -> str:
        """格式化日期（Java: `new SimpleDateFormat("yyyy/MM/dd").format(date)`）。"""
        # 【Java→Python】Java 每次调用都 new 一个 SimpleDateFormat（线程安全性考虑），
        # 替身保持同样写法：每次新建，不做缓存。
        sdf: SimpleDateFormat = SimpleDateFormat("yyyy/MM/dd")
        return sdf.format(date)
