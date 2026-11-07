#pragma once
// Java 实体（MyBatis resultMap / Jackson 契约）在 C++ 侧的数据描述。
// 之所以用“元数据 + 动态 JSON 行”而不是为 22 张表手写 22 个结构体：
//   * Jackson 输出的字段集合/顺序由 Java 类字段声明顺序决定，
//     entities_generated.h 已按该顺序完整生成；
//   * 列表接口只 SELECT 部分列，未查询的列在 Java 侧同样是 null，
//     动态行可以精确复现“全字段 + null 填充”的序列化结果；
//   * 过滤条件（@RequestParam 绑定到实体属性）在 MyBatis XML 中
//     是固定的 if 链，用 FilterMeta 描述即可一一对应。
#include <algorithm>
#include <string>
#include <vector>

namespace cm::meta {

// 对应 Java 字段类型；决定 JSON 编码方式。
enum class FType {
  Str,       // String
  Int,       // Integer / int
  JavaLong,  // Long / long  -> 数字（Jackson 默认不做字符串化）
  Double,    // Double / double
  Decimal,   // BigDecimal -> 保留数据库标度
  Timestamp, // java.util.Date 无 @JsonFormat -> ISO-8601（UTC）
  DateTime,  // @JsonFormat("yyyy-MM-dd HH:mm:ss")
  Day,       // @JsonFormat("yyyy-MM-dd")
  Json       // JSON 文本 / 对象
};

// 对应 MyBatis XML 中 <if> 的条件运算符。
enum class FOp {
  Eq,     // col = val
  Like,   // col like concat('%', val, '%')
  ILike,  // col ilike concat('%', val, '%')
  In,     // col in (...)
  Gte,    // col >= val
  Lte,    // col <= val
  Gt,
  Lt
};

struct FieldMeta {
  std::string json;    // Java 属性名（JSON key）
  std::string column;  // 结果集列名（可为空：仅存在于 Java 类、无对应列）
  FType type;
  bool pk;
};

struct FilterMeta {
  std::string json;    // Java 属性名
  std::string column;  // 物理列名
  FOp op;
};

struct EntityMeta {
  std::string name;       // Java 类名
  std::string table;      // schema.table
  std::string select_sql; // mapper XML 的 <sql id="...Vo"> 片段
  std::string order_sql;  // 列表查询默认 ORDER BY 片段（不含 "order by"）
  std::vector<FieldMeta> fields;
  std::vector<FilterMeta> filters;
};

// 实际使用的 SELECT 列清单：
//   * select_sql 为显式列清单时原样返回；
//   * select_sql 为 "*" 时按 fields 的物理列展开（跳过无物理列的 Java-only 字段，
//     并按列名去重），使查询只取 resultMap 需要的列。
inline std::string select_columns(const EntityMeta& m) {
  if (m.select_sql != "*") return m.select_sql;
  std::string out;
  std::vector<std::string> seen;
  for (const auto& f : m.fields) {
    if (f.column.empty()) continue;
    if (std::find(seen.begin(), seen.end(), f.column) != seen.end()) continue;
    seen.push_back(f.column);
    if (!out.empty()) out += ",\n\t";
    out += f.column;
  }
  return out.empty() ? "*" : out;
}

} // namespace cm::meta
