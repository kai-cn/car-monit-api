package com.ruoyi.base.agent.tools;

import com.ruoyi.base.agent.core.AgentPrincipal;

import java.util.List;

/**
 * 工具目录：与框架无关的单一事实源。
 *
 * <p>用途：</p>
 * <ul>
 *   <li>{@code GET /api/v1/agent/tools} 对外暴露能力清单；</li>
 *   <li>启动时校验框架实际注册的工具名与目录一致，防止契约漂移；</li>
 *   <li>设计/Spec 文档与代码同源，评审时可直接比对。</li>
 * </ul>
 */
public final class AgentToolCatalog {

    public enum Risk {
        READ, WRITE
    }

    public record ToolSpec(String name, String description, Risk risk, String requiredRoles, String inputSchema) {
    }

    private AgentToolCatalog() {
    }

    public static final String QUERY_TRAFFIC = "query_traffic_records";
    public static final String VEHICLE_TRACK = "get_vehicle_track";
    public static final String BIGSCREEN_METRIC = "get_bigscreen_metric";
    public static final String SEARCH_KNOWLEDGE = "search_knowledge";
    public static final String SUBMIT_EXPORT = "submit_export";
    public static final String EXPORT_STATUS = "get_export_status";
    public static final String DATA_QUALITY = "get_data_quality";

    private static final List<ToolSpec> SPECS = List.of(
            new ToolSpec(QUERY_TRAFFIC,
                    "查询高速公路通行/收费/轨迹元数据。适用于：某时间段某车牌、某路段/门架/收费站的流水与抓拍记录。"
                            + "返回总量、是否还有下一页和最多 20 行明细；全量数据请引导用户使用页面查询或导出。",
                    Risk.READ, "ops,audit,admin", """
                    {
                      "type": "object",
                      "properties": {
                        "table": {"type": "string", "enum": ["snapshot", "fee", "trail"],
                          "description": "snapshot=门架/省界/收费站抓拍；fee=收费流水；trail=轨迹拟合元数据"},
                        "start_time": {"type": "string", "description": "开始时间，yyyy-MM-dd HH:mm:ss 或 yyyy-MM-dd；缺省为结束时间前 7 天"},
                        "end_time": {"type": "string", "description": "结束时间；缺省为当前时间"},
                        "plate": {"type": "string", "description": "车牌，可含颜色后缀如 赣B21E85_0；至少 2 个字符"},
                        "color_code": {"type": "string", "description": "车牌颜色码（收费表可选）"},
                        "org_codes": {"type": "array", "items": {"type": "string"}, "description": "管理单位编码，多值"},
                        "section_codes": {"type": "array", "items": {"type": "string"}, "description": "路段编码，多值"},
                        "road_codes": {"type": "array", "items": {"type": "string"}, "description": "道路编码，多值"},
                        "gantry_codes": {"type": "array", "items": {"type": "string"}, "description": "门架编码，多值"},
                        "toll_codes": {"type": "array", "items": {"type": "string"}, "description": "收费站编码，多值"},
                        "page_size": {"type": "integer", "minimum": 1, "maximum": 50, "description": "返回行数，默认 20"},
                        "page_num": {"type": "integer", "minimum": 1, "maximum": 10, "description": "页码，默认 1"}
                      },
                      "required": ["table"]
                    }
                    """),
            new ToolSpec(VEHICLE_TRACK,
                    "按车牌和时间段回放车辆轨迹（门架/省界/收费站抓拍点 + 经纬度）。"
                            + "适用于：核查车辆行驶路径、判断是否绕行/逃费。单次时间窗不超过 24 小时，最多返回 200 个点。",
                    Risk.READ, "audit,admin", """
                    {
                      "type": "object",
                      "properties": {
                        "plate": {"type": "string", "description": "车牌，可含颜色后缀"},
                        "start_time": {"type": "string", "description": "开始时间；缺省为结束时间前 6 小时"},
                        "end_time": {"type": "string", "description": "结束时间；缺省为当前时间"},
                        "max_points": {"type": "integer", "minimum": 20, "maximum": 200, "description": "最大轨迹点数量，默认 200"}
                      },
                      "required": ["plate"]
                    }
                    """),
            new ToolSpec(BIGSCREEN_METRIC,
                    "查询大屏预聚合指标：逃费统计、稽核统计、收入分布、告警 TopN。"
                            + "适用于：运营日报、值班问答中的汇总数字，不返回明细流水。",
                    Risk.READ, "ops,audit,admin", """
                    {
                      "type": "object",
                      "properties": {
                        "metric": {"type": "string", "enum": ["escape", "audit", "income", "warning_top"],
                          "description": "escape=逃费；audit=稽核；income=收入；warning_top=告警 TopN"},
                        "start_date": {"type": "string", "description": "开始日期 yyyy-MM-dd"},
                        "end_date": {"type": "string", "description": "结束日期 yyyy-MM-dd"},
                        "org_id": {"type": "string", "description": "管理单位 ID（escape 可选）"},
                        "escaped_type": {"type": "string", "description": "逃费类型（escape 可选）"},
                        "query_date_type": {"type": "string", "description": "income 的日期口径，如 day/month"},
                        "top_n": {"type": "integer", "minimum": 1, "maximum": 50, "description": "warning_top 的 N，默认 10"}
                      },
                      "required": ["metric"]
                    }
                    """),
            new ToolSpec(SEARCH_KNOWLEDGE,
                    "检索数据字典、指标口径、表结构、查询限制和常见问题。"
                            + "适用于：解释字段含义、确认指标算法、回答“为什么查不到数据”等知识型问题。返回带出处的片段。",
                    Risk.READ, "ops,audit,admin", """
                    {
                      "type": "object",
                      "properties": {
                        "query": {"type": "string", "description": "要检索的问题或关键词"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 5, "description": "返回片段数，默认 3"}
                      },
                      "required": ["query"]
                    }
                    """),
            new ToolSpec(SUBMIT_EXPORT,
                    "提交导出任务（异步）。高风险写操作：必须由用户在界面二次确认后，"
                            + "客户端在请求中携带 confirmToken 才会执行；模型不得自行调用。",
                    Risk.WRITE, "admin", """
                    {
                      "type": "object",
                      "properties": {
                        "table": {"type": "string", "enum": ["snapshot", "fee", "trail"]},
                        "start_time": {"type": "string", "description": "开始时间"},
                        "end_time": {"type": "string", "description": "结束时间"},
                        "mode": {"type": "string", "enum": ["display", "full"], "description": "display=展示字段；full=全字段"},
                        "plate": {"type": "string", "description": "车牌（可选）"},
                        "fields": {"type": "array", "items": {"type": "string"}, "description": "展示字段白名单（可选）"},
                        "purpose": {"type": "string", "description": "导出用途，写入审计，必填"}
                      },
                      "required": ["table", "start_time", "end_time", "purpose"]
                    }
                    """),
            new ToolSpec(EXPORT_STATUS,
                    "查询导出任务进度与下载就绪状态。只允许查询本人提交的任务（管理员除外）。",
                    Risk.READ, "ops,audit,admin", """
                    {
                      "type": "object",
                      "properties": {
                        "task_id": {"type": "string", "description": "导出任务 ID"}
                      },
                      "required": ["task_id"]
                    }
                    """),
            new ToolSpec(DATA_QUALITY,
                    "数据质量诊断：统计指定时间窗内的上报量、入库量、丢失率、重复量。"
                            + "适用于：回答“今天数据全不全/为什么少了”等问题。时间窗不超过 24 小时。",
                    Risk.READ, "ops,audit,admin", """
                    {
                      "type": "object",
                      "properties": {
                        "start_time": {"type": "string", "description": "开始时间"},
                        "end_time": {"type": "string", "description": "结束时间"}
                      },
                      "required": ["start_time", "end_time"]
                    }
                    """)
    );

    public static List<ToolSpec> specs() {
        return SPECS;
    }

    public static boolean contains(String name) {
        return SPECS.stream().anyMatch(s -> s.name().equals(name));
    }

    public static ToolSpec find(String name) {
        return SPECS.stream().filter(s -> s.name().equals(name)).findFirst().orElse(null);
    }

    /**
     * 主体是否具备调用该工具的角色。
     *
     * <p>角色校验放在工具层（而不是提示词或适配层）的原因：模型可能被诱导调用任意工具，
     * 提示词只是"建议"，真正的授权必须在服务端按 {@code requiredRoles} 判定。
     * 未登记的工具一律拒绝（默认拒绝优于默认放行）。</p>
     */
    public static boolean allows(AgentPrincipal principal, String name) {
        ToolSpec spec = find(name);
        if (spec == null || principal == null) {
            return false;
        }
        for (String role : spec.requiredRoles().split(",")) {
            String r = role.trim();
            if (!r.isEmpty() && principal.hasRole(r)) {
                return true;
            }
        }
        return false;
    }
}
