package handler

// JAVA 对照:
//
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsLwzxsfsjFeeRecords01Controller.java:50-55
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsRtSzdnSnapshotFlowAddcodeController.java:44-56
//	pro-base-common/src/main/java/com/ruoyi/common/utils/CommonUtil.java（isNull/isNotBlank/deleteEnd）
//
// 类/职责: handler 层共用的小工具 —— 查询范围开关、逗号串展开
// 对应 Go 文件: internal/handler/common.go
// 关键映射:
//
//	redisCache.getCacheObject("sys_config:data_query") → inQueryAllScope
//	Arrays.stream(s.split(",")).collect(...)          → splitCSV
//
// DIFF: Java 里这两个片段被复制到多个 Controller；Go 收成两个函数，避免某天一个接口改了、
// 另一个接口还是老逻辑（这正是 Java 侧 feerecords/snapshotflow 各两份循环的老问题）。

import (
	"context"
	"strings"

	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

// inQueryAllScope 对应 Controller 里的这段：
//
//	String queryQx = "noall";
//	String dataQuery = CommonUtil.isNull(redisCache.getCacheObject("sys_config:data_query"));
//	if (CommonUtil.isNotBlank(dataQuery)) { queryQx = dataQuery; }
//	if (!queryQx.equals("queryall")) { ...数据权限... }
//
// 返回 true 表示“查询全部”，即不需要追加数据权限条件。
//
// PARITY: Redis 不可用时 Java 会抛异常（整个接口 500）；这里按“读不到 = noall”降级，
// 也就是更严格的数据权限 —— 宁可多过滤，也不因为缓存抖动把全省数据放出去。
//
// 注意必须走 GetText 而不是 Get：Redis 里存的是 FastJson2 写出的 JSON 字面量
// "queryall"（带双引号），拿裸字节去比 queryall 永远不相等，结果就是全网所有列表接口
// 都被额外加上 JiAnDong 数据权限条件（实测 /base/snapshotflow/list 的 total 会从 900 变成 251）。
func (d *BaseDeps) inQueryAllScope(ctx context.Context) bool {
	if d.Cache == nil {
		return false
	}
	raw, ok, err := d.Cache.GetText(ctx, sysConfigDataQuery)
	if err != nil || !ok {
		return false
	}
	return strings.EqualFold(strings.TrimSpace(raw), "queryall")
}

// splitCSV 对应 `Arrays.stream(s.split(",")).collect(Collectors.toList())`。
// 空段会被丢掉（Java 的 split 会保留空段，但后续 <foreach> 里空串不影响 IN 结果）。
func splitCSV(s string) []string {
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if p = strings.TrimSpace(p); utils.IsNotBlank(p) {
			out = append(out, p)
		}
	}
	return out
}
