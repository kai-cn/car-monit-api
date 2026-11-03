#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JAVA -> GO 数据访问层（Repository）代码生成器
==============================================

输入：pro-business-api/src/main/java/com/ruoyi/base/mapper/*.java + domain/*
输出：car-monit-api-go/internal/repo/<table>.go

为什么需要生成
--------------
Java 侧 22 个 Mapper 全部 `extends BaseMapper<T>`，CRUD 是 MyBatis-Plus 提供的"零代码"能力；
Go 侧没有等价框架魔法，必须把 GetByID/List/Insert/Update/Delete 显式写出来。
这些方法体高度同构，手写 22 遍既浪费时间又容易漏字段，因此生成。

重要差异（必须在 README 里同步）
-------------------------------
Java 仓库里 `resources/mapper/xml` 只有 PulsarMessageRecordMapper.xml 一个文件，
其余 Mapper 的自定义方法（selectXxxList / selectByCursorShard ...）没有对应 SQL。
也就是说 **Java 侧这些方法在运行期是残缺的**。
本生成器按字段语义重建查询条件（name/plate → ILIKE，code/id → 精确匹配，applyTime1/2 → 时间区间），
并在每个 List 方法上标注 `// PARITY:` 说明重建依据。
"""

import os

from gen_models import BASE, JAVA_DIR, parse_file, snake

OUT_DIR = os.path.join(BASE, "internal", "repo")
MAPPER_DIR = os.path.join(
    os.path.dirname(BASE),
    "pro-business-api", "src", "main", "java", "com", "ruoyi", "base", "mapper",
)

# 每张表的查询语义（缺失 XML 的重建依据）。键是 Java 类名。
SPEC = {
    "OdsRtSzdnSnapshotFlowAddcode": {
        "time": [("snapshottime", "applyTime1", "applyTime2")],
        "fuzzy": ["platenumber", "gantryname", "roadname", "sectionname", "orgname",
                  "tollname", "gantrycode", "tollcode", "deviceid", "datauuid"],
    },
    "OdsLwzxsfsjFeeRecords01": {
        "time": [("inapplytime", "inApplyTime1", "inApplyTime2")],
        "fuzzy": ["vehicleplate", "gantryname", "roadname", "sectionname", "orgname", "tollname"],
    },
    "ZdataTrailFitting": {
        "time": [("entime", "startTime", "endTime"), ("extime", "startTime", "endTime")],
        "fuzzy": ["platekey", "platenumber", "roadname", "sectionname"],
    },
    "ZdataTrailTracks": {
        "time": [("createtime", "applyTime1", "applyTime2")],
        "fuzzy": ["platekey", "trailuuid"],
    },
    "OdsRtSzdnSnapshotFlowProvcaptureAddcode": {
        "time": [("snapshottime", "applyTime1", "applyTime2")],
        "fuzzy": ["platenumber", "gantryname", "roadname", "sectionname", "orgname", "tollname"],
    },
    "OdsRtSzdnSnapshotFlowStationcaptureAddcode": {
        "time": [("snapshottime", "applyTime1", "applyTime2")],
        "fuzzy": ["platenumber", "gantryname", "tollname", "sectionname"],
    },
    "OdsSzdnProvinceBorderVehicleWeightNewstructure": {
        "time": [("weighingtime", "applyTime1", "applyTime2")],
        "fuzzy": ["platenumber", "gantryname", "roadname", "sectionname"],
    },
    "OdsCxztFwqclls": {
        "time": [("snapshottime", "applyTime1", "applyTime2")],
        "fuzzy": ["platenumber", "sectionname", "orgname"],
    },
}

# 常见的"时间区间入参 → 表的哪一列"兜底规则
FALLBACK_TIME_COLS = [
    "snapshottime", "inapplytime", "applytime", "entime", "createtime",
    "receivedtime", "loadtime", "weighingtime",
]


def pick_spec(spec):
    """返回 (time_pairs, fuzzy_fields)，都转成 Java 字段名"""
    fields = {f["name"]: f for f in spec["fields"]}
    lower = {snake(n): n for n in fields}

    if spec["class"] in SPEC:
        cfg = SPEC[spec["class"]]
        time_pairs = [(c, a, b) for (c, a, b) in cfg["time"] if c in lower and a in fields and b in fields]
        fuzzy = [f for f in cfg["fuzzy"] if f in fields]
        return time_pairs, fuzzy

    # 通用推断：找一对 xxx1/xxx2 的时间入参
    time_pairs = []
    time_col = next((lower[c] for c in FALLBACK_TIME_COLS if c in lower), None)
    for name in fields:
        if name.endswith("1") and (name[:-1] + "2") in fields and ("time" in name.lower()):
            if time_col:
                time_pairs.append((snake(time_col), name, name[:-1] + "2"))
            break
    fuzzy = [n for n in fields
             if ("name" in n.lower() and not n.endswith("Str")) or n.lower().startswith("plate")]
    return time_pairs, fuzzy


def go_zero(field):
    """判断该字段是否为"零值即不过滤"的类型"""
    return field["type"] in ("String", "Integer", "Long")


def emit(spec, rel_mapper):
    cls = spec["class"]
    rep = cls + "Repo"
    table_full = ('%s.%s' % (spec["schema"], spec["table"])) if spec["schema"] else spec["table"]
    pk_col = spec["pk"] or "big_id"
    pk_field = next((f for f in spec["fields"] if snake(f["name"]) == pk_col), None)
    pk_go_field = pk_field["name"][:1].upper() + pk_field["name"][1:] if pk_field else "BigId"
    pk_type = "string"
    if pk_field and pk_field["type"] in ("Long", "Integer"):
        pk_type = "int64" if pk_field["type"] == "Long" else "int"
    time_pairs, fuzzy = pick_spec(spec)

    out = [
        "package repo",
        "",
        "// JAVA 对照: %s" % rel_mapper,
        "// 类/职责: %sMapper — 表 %s 的数据访问入口" % (cls, spec["table"]),
        "// 对应 Go 文件: internal/repo/%s.go" % snake(cls),
        "// 关键映射:",
        "//   extends BaseMapper<%s>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）" % cls,
        "//   select%sById(%s)   → GetByID" % (cls, pk_go_field),
        "//   select%sList(%s q) → List/Count（条件见 apply%sFilters）" % (cls, cls, cls),
        "// DIFF: Java 用 XML/注解把 SQL 与接口解耦；Go 把 SQL 写在方法里，好在编译期就能发现列名/类型不匹配。",
        "// PARITY: Java 侧 resources/mapper/xml 中缺少本 Mapper 的 XML，selectList 的实际 SQL 无从对照；",
        "//         这里按字段语义重建（name/plate → ILIKE，code/id → 精确，applyTime1/2 → 时间区间）。",
        "",
        "import (",
        '\t"context"',
        '\t"fmt"',
        '\t"strings"',
        "",
        '\t"gorm.io/gorm"',
        "",
        '\t"github.com/ruoyi/car-monit-api-go/internal/db"',
        '\t"github.com/ruoyi/car-monit-api-go/internal/model"',
        ")",
        "",
        "// %sTable 对应 Java @TableName(value = %r, schema = %r)" % (cls, spec["table"], spec["schema"]),
        'const %sTable = "%s"' % (cls, table_full),
        "",
        "// %s 对应 Java 的 %sMapper（@Repository 由 main() 里的显式构造代替）" % (rep, cls),
        "type %s struct{ db *db.Client }" % rep,
        "",
        "// New%s 对应 Spring @Repository 的 Bean 注册" % rep,
        "func New%s(c *db.Client) *%s { return &%s{db: c} }" % (rep, rep, rep),
        "",
        "// TableName 供测试与日志使用",
        "func (r *%s) TableName() string { return %sTable }" % (rep, cls),
        "",
        "// GetByID 对应 %sMapper.select%sById(%s)" % (cls, cls, pk_go_field),
        "func (r *%s) GetByID(ctx context.Context, id %s) (*model.%s, error) {" % (rep, pk_type, cls),
        "\tvar m model.%s" % cls,
        "\terr := r.db.ORM(ctx).Table(%sTable).Where(\"%s = ?\", id).Take(&m).Error" % (cls, pk_col),
        "\tif err != nil {",
        "\t\tif err == gorm.ErrRecordNotFound {",
        "\t\t\treturn nil, nil",
        "\t\t}",
        '\t\treturn nil, fmt.Errorf("%s.GetByID: %%w", err)' % rep,
        "\t}",
        "\treturn &m, nil",
        "}",
        "",
        "// List 对应 %sMapper.select%sList(q)" % (cls, cls),
        "// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。",
        "func (r *%s) List(ctx context.Context, q *model.%s, limit int) ([]model.%s, error) {" % (rep, cls, cls),
        "\ttx := apply%sFilters(r.db.ORM(ctx).Table(%sTable), q)" % (cls, cls),
        "\tif limit > 0 {",
        "\t\ttx = tx.Limit(limit)",
        "\t}",
        "\tvar list []model.%s" % cls,
        "\tif err := tx.Find(&list).Error; err != nil {",
        '\t\treturn nil, fmt.Errorf("%s.List: %%w", err)' % rep,
        "\t}",
        "\treturn list, nil",
        "}",
        "",
        "// Count 对应 select%sList 配合 PageInfo#getTotal" % cls,
        "func (r *%s) Count(ctx context.Context, q *model.%s) (int64, error) {" % (rep, cls),
        "\ttx := apply%sFilters(r.db.ORM(ctx).Table(%sTable), q)" % (cls, cls),
        "\tvar n int64",
        "\tif err := tx.Count(&n).Error; err != nil {",
        '\t\treturn 0, fmt.Errorf("%s.Count: %%w", err)' % rep,
        "\t}",
        "\treturn n, nil",
        "}",
        "",
        "// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）",
        "func (r *%s) ListAll(ctx context.Context) ([]model.%s, error) {" % (rep, cls),
        "\tvar list []model.%s" % cls,
        "\tif err := r.db.ORM(ctx).Table(%sTable).Find(&list).Error; err != nil {" % cls,
        '\t\treturn nil, fmt.Errorf("%s.ListAll: %%w", err)' % rep,
        "\t}",
        "\treturn list, nil",
        "}",
        "",
        "// Insert 对应 BaseMapper.insert(entity)",
        "func (r *%s) Insert(ctx context.Context, m *model.%s) error {" % (rep, cls),
        "\tif err := r.db.ORM(ctx).Table(%sTable).Create(m).Error; err != nil {" % cls,
        '\t\treturn fmt.Errorf("%s.Insert: %%w", err)' % rep,
        "\t}",
        "\treturn nil",
        "}",
        "",
        "// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量",
        "// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。",
        "func (r *%s) BatchInsert(ctx context.Context, list []*model.%s, batchSize int) error {" % (rep, cls),
        "\tif len(list) == 0 {",
        "\t\treturn nil",
        "\t}",
        "\tif batchSize <= 0 {",
        "\t\tbatchSize = 500",
        "\t}",
        "\treturn r.db.ORM(ctx).Table(%sTable).CreateInBatches(list, batchSize).Error" % cls,
        "}",
        "",
        "// Update 对应 BaseMapper.updateById(entity)",
        "func (r *%s) Update(ctx context.Context, m *model.%s) error {" % (rep, cls),
        "\tif err := r.db.ORM(ctx).Table(%sTable).Save(m).Error; err != nil {" % cls,
        '\t\treturn fmt.Errorf("%s.Update: %%w", err)' % rep,
        "\t}",
        "\treturn nil",
        "}",
        "",
        "// DeleteByID 对应 BaseMapper.deleteById(id)",
        "func (r *%s) DeleteByID(ctx context.Context, id %s) error {" % (rep, pk_type),
        "\tif err := r.db.ORM(ctx).Table(%sTable).Where(\"%s = ?\", id).Delete(&model.%s{}).Error; err != nil {" % (
            cls, pk_col, cls),
        '\t\treturn fmt.Errorf("%s.DeleteByID: %%w", err)' % rep,
        "\t}",
        "\treturn nil",
        "}",
        "",
        "// apply%sFilters 把 Java 侧 XML <if test=\"...\"> 的条件重建为 Go 代码。" % cls,
        "// 为空即不过滤，语义与 MyBatis 的 <if> 一致。",
        "func apply%sFilters(tx *gorm.DB, q *model.%s) *gorm.DB {" % (cls, cls),
        "\tif q == nil {",
        "\t\treturn tx",
        "\t}",
    ]

    # 只有真正落库的字段才能出现在 WHERE 里；@TableField(exist=false) 的临时字段必须排除
    field_types = {f["name"]: f["type"] for f in spec["fields"] if not f["transient"]}
    for col, start, end in time_pairs:
        st = start[:1].upper() + start[1:]
        et = end[:1].upper() + end[1:]
        out.append("\tif q.%s != \"\" {" % st)
        out.append("\t\ttx = tx.Where(\"%s >= ?\", q.%s)" % (col, st))
        out.append("\t}")
        out.append("\tif q.%s != \"\" {" % et)
        out.append("\t\ttx = tx.Where(\"%s <= ?\", q.%s)" % (col, et))
        out.append("\t}")
    for name in fuzzy:
        gof = name[:1].upper() + name[1:]
        ftype = field_types.get(name, "String")
        if ftype != "String" or name not in field_types:
            continue
        out.append("\tif q.%s != \"\" {" % gof)
        out.append("\t\ttx = tx.Where(\"%s ILIKE ?\", \"%%\"+q.%s+\"%%\")" % (snake(name), gof))
        out.append("\t}")

    # 精确匹配：车牌之外的 code/id/uuid 字段
    exact = [n for n, t in field_types.items()
             if t == "String" and (n.lower().endswith("code") or n.lower().endswith("id")
                                   or n.lower().endswith("uuid"))
             and n not in fuzzy and n not in ("applyTime1", "applyTime2", "inApplyTime1", "inApplyTime2")]
    for name in exact[:12]:
        gof = name[:1].upper() + name[1:]
        out.append("\tif q.%s != \"\" {" % gof)
        out.append("\t\ttx = tx.Where(\"%s = ?\", q.%s)" % (snake(name), gof))
        out.append("\t}")
    if not time_pairs and not fuzzy and not exact:
        out.append("\t_ = tx")
        out.append("\t// PARITY: 该表没有可推断的查询入参，List 等价于无条件查询")
    out.append("\treturn tx")
    out.append("}")
    out.append("")
    return "\n".join(out)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    count = 0
    for fn in sorted(os.listdir(JAVA_DIR)):
        if not fn.endswith(".java"):
            continue
        spec = parse_file(os.path.join(JAVA_DIR, fn))
        if not spec["table"]:
            continue  # 纯 VO 无表，不需要 Repo
        mapper_file = spec["class"] + "Mapper.java"
        rel = "pro-business-api/src/main/java/com/ruoyi/base/mapper/%s" % mapper_file
        code = emit(spec, rel)
        path = os.path.join(OUT_DIR, snake(spec["class"]) + ".go")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(code)
        count += 1
        print("generated repo %-50s ← %s" % (os.path.basename(path), mapper_file))
    print("\n共生成 %d 个 repo 文件 → %s" % (count, OUT_DIR))


if __name__ == "__main__":
    main()
