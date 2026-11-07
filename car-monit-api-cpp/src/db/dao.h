#pragma once
// MyBatis Mapper + PageHelper 的通用实现。
//
// 每个实体由 EntityMeta 描述其 SELECT 列、表名、过滤条件与默认排序；
// 列表接口的行为与 XML <select id="...List"> + PageHelper 一致：
//   * 请求带 pageNum/pageSize 时执行 count + limit/offset，越界按 reasonable=true 夹到末页
//   * 请求带 orderByColumn/isAsc 时追加排序（列名经 SqlUtil 白名单/下划线校验）
//   * 未带分页参数时返回全量
#include "common/json.h"
#include "db/pg.h"
#include "http/ctx.h"
#include "meta/entity_meta.h"

#include <map>
#include <optional>
#include <string>
#include <vector>

namespace cm::repo {

struct PageInfo {
  bool paged = false;
  int page_num = 1;
  int page_size = 10;
  std::string order_by; // 已校验的 "col asc"
};

// BaseController.startPage() 的等价实现。
PageInfo resolve_page(const http::Request& req);

// 单行 -> JSON（字段顺序由 EntityMeta 决定；未出现在结果集的列输出 null）。
Json project_row(const meta::EntityMeta& meta, const db::PgResult& result, std::size_t row);

// 按 FilterMeta 生成 WHERE 条件（"AND col = 'x'" 形式）；不存在的参数跳过。
std::string where_from_filters(const meta::EntityMeta& meta, const http::Request& req,
                               const std::vector<std::pair<std::string, std::string>>& extra = {});

std::string quote(const std::string& value);
std::string in_list(const std::vector<std::string>& values);

// 通用查询：构造 SQL 并执行。
//   extra_where: 追加条件（以 " AND " 开头，可为空）
//   columns_override: 覆盖 EntityMeta.select_sql（可选）
Json select_list(const meta::EntityMeta& meta, const http::Request& req,
                 const std::string& extra_where = "",
                 const std::optional<std::string>& columns_override = std::nullopt);

// 按主键查询（主键取 EntityMeta 中第一个 pk 字段）。
Json select_by_id(const meta::EntityMeta& meta, const std::string& id);

// 按主键批量查询：ids 为逗号分隔；返回数组。
Json select_by_ids(const meta::EntityMeta& meta, const std::string& ids);

// 执行任意列表 SQL（分页语义同上），用于 mapper 自定义多表查询。
Json select_list_raw(const std::string& base_sql, const http::Request& req);

// 执行 count。
long long count_rows(const std::string& from_and_where);

} // namespace cm::repo
