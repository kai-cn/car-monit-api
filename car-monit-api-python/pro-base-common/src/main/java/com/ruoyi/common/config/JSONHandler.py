# -*- coding: utf-8 -*-
"""com.ruoyi.common.config.JSONHandler

源文件：pro-base-common/src/main/java/com/ruoyi/common/config/JSONHandler.java

【Java→Python】整体说明
1) 本类是 MyBatis 的 TypeHandler（``extends BaseTypeHandler<T>``），负责把
   Java 对象 ↔ 数据库 VARCHAR 列互转。Python 没有 MyBatis，``BaseTypeHandler``
   退化为本模块的 ``BaseTypeHandler`` 抽象基类，仅保留同名方法签名，
   供 ``com.ruoyi.base.mapper.*`` 的 Python 映射层调用。
2) ``ObjectMapper``（Jackson）→ 标准库 ``json``：
   - ``setSerializationInclusion(NON_NULL)`` → 序列化时跳过值为 None 的字段；
   - ``JsonParser.Feature.ALLOW_MISSING_VALUES=false`` → json.loads 默认行为即严格模式。
3) ``@MappedTypes({Object.class})`` / ``@MappedJdbcTypes(JdbcType.VARCHAR)`` 是注解式
   类型注册，Python 用类属性 ``MAPPED_TYPES`` / ``MAPPED_JDBC_TYPES`` 表达。
4) ``PreparedStatement/ResultSet/CallableStatement`` 是 JDBC 接口，Python 侧用
   鸭子类型（要求 ``setString``/``getString``）以免绑死某个驱动。
5) ``@Slf4j`` → 模块级 logging.getLogger。
"""
from __future__ import annotations

import dataclasses
import json
import logging
from typing import Any, Optional

log = logging.getLogger(__name__)


class JdbcType:
    """org.apache.ibatis.type.JdbcType 的最小替身，只保留本类用到的 VARCHAR。"""

    VARCHAR = "VARCHAR"


class BaseTypeHandler:
    """MyBatis ``BaseTypeHandler<T>`` 的 Python 抽象替身。

    Java 侧由 MyBatis 在查询/写入时回调；Python 侧由 mapper 层显式调用同名方法，
    这样业务代码的调用点写法保持一致。
    """

    def setNonNullParameter(self, prepared_statement: Any, i: int, t: Any,
                            jdbc_type: Optional[str]) -> None:
        raise NotImplementedError

    def getNullableResult(self, result_set: Any, key: Any) -> Any:
        raise NotImplementedError

    def get_result(self, result_set: Any, key: Any) -> Any:
        """MyBatis 在值为 NULL 时的短路逻辑：null 不进 getNullableResult。"""
        value = result_set.getObject(key)
        if value is None:
            return None
        return self.getNullableResult(result_set, key)


class JSONHandler(BaseTypeHandler):
    """对象 ↔ JSON 字符串的 MyBatis 类型处理器。

    【Java→Python】
    Java 的 ``Class<T> clazz`` 构造参数在 Python 用 type 对象传入；
    ``T extends Object`` 的泛型上界无运行期含义，忽略。
    """

    # @MappedTypes({Object.class}) / @MappedJdbcTypes(JdbcType.VARCHAR)
    MAPPED_TYPES = [object]
    MAPPED_JDBC_TYPES = JdbcType.VARCHAR

    def __init__(self, clazz: Any) -> None:
        if clazz is None:
            # Java: throw new NullPointerException("Type argument cannot be null")
            raise NullPointerException("Type argument cannot be null")
        self.clazz = clazz

    # ------------------------------------------------------------------ 内部方法
    def toJSON(self, obj: Any) -> Optional[str]:
        """object 转 json string；异常时返回 null（异常被吞掉并打日志，保持原样）。"""
        try:
            string = json.dumps(self._to_compatible(obj), ensure_ascii=False, default=str)
            log.info(">>>> json handler string:%s <<<<", string)
            return string
        except Exception as e:
            log.error(">>>> covert object to json string failed, error message: <<<<%s", e)
        return None

    def toObject(self, json_str: Optional[str], clazz: Any) -> Any:
        """json 转 object。

        【Java→Python】原 Java 判断 ``json != null && json != ""`` 是**引用比较**，
        对 String 恒为 true（缺陷）；这里按“空串不解析”的直觉实现，并在注释中保留说明。
        """
        if json_str is not None and json_str != "":
            data = json.loads(json_str)
            return self._from_compatible(data, clazz)
        return None

    @staticmethod
    def _to_compatible(obj: Any) -> Any:
        """对应 Jackson 的 NON_NULL 序列化策略：None 字段直接丢弃。"""
        if obj is None:
            return None
        if isinstance(obj, dict):
            return {k: JSONHandler._to_compatible(v) for k, v in obj.items() if v is not None}
        if isinstance(obj, (list, tuple)):
            return [JSONHandler._to_compatible(v) for v in obj]
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            result = {}
            for field in dataclasses.fields(obj):
                value = getattr(obj, field.name)
                if value is None:
                    continue
                result[field.name] = JSONHandler._to_compatible(value)
            return result
        if hasattr(obj, "__dict__"):
            return {k: JSONHandler._to_compatible(v)
                    for k, v in vars(obj).items() if v is not None}
        return obj

    @staticmethod
    def _from_compatible(data: Any, clazz: Any) -> Any:
        if data is None or clazz is None:
            return data
        if isinstance(clazz, type) and dataclasses.is_dataclass(clazz):
            allowed = {f.name for f in dataclasses.fields(clazz)}
            return clazz(**{k: v for k, v in data.items() if k in allowed})
        if isinstance(clazz, type) and isinstance(data, dict):
            try:
                return clazz(**data)
            except TypeError:
                return data
        return data

    # ------------------------------------------------------------------ 回调方法
    def setNonNullParameter(self, prepared_statement: Any, i: int, t: Any,
                            jdbc_type: Optional[str]) -> None:
        try:
            prepared_statement.setString(i, self.toJSON(t))
        except Exception as e:
            log.error(">>>> preparedStatement set string failed, error message:%s <<<<", e)

    def getNullableResult(self, result_set: Any, key: Any) -> Any:
        """三个 Java 重载（String 列名 / int 列序号 / CallableStatement）合并为一个。

        【Java→Python】key 既可以是列名（str）也可以是列序号（int），
        JDBC 驱动按类型分派，这里统一透传给 result_set.getString。
        """
        try:
            return self.toObject(result_set.getString(key), self.clazz)
        except ValueError as e:
            # 对应 IOException：JSON 解析失败
            log.error(">>>> convert json string to object failed, error message:%s <<<<", e)
        return None


class NullPointerException(Exception):
    """java.lang.NullPointerException 的 Python 替身（仅为保持异常语义一致）。"""
