package handler

// JAVA 对照:
//
//	pro-business-api/src/main/java/com/ruoyi/base/controller/SysTestController.java:22-368
//
// 类/职责: 运维/自测端点（/base/sysutilTest/*），生产上由定时任务或运维手工触发
// 对应 Go 文件: internal/handler/selftest.go
// 关键映射:
//
//	15 个 @GetMapping              → 15 条路由，路径逐条一致（本文件 + blockedEndpoints）
//	/syncBaseInfo                  → DictRegistry.RefreshAll（= 7 个 updateRedis() 的合并）
//	/syncCurrentTrack              → SysUtilService.SyncTrack（= SyncUtilServiceImpl.syncTrack）
//	/syncHistroyTrack              → SysUtilService.SyncHistoryTrack（= 主体在 Controller 里，见 TrackTask）
//	其余 12 个                      → 501 + 逐条写明「为什么不能移」（见 blockedEndpoints）
//
// DIFF: Java 这个 Controller 直接注入 12 个 Service 并在方法体里写整段批处理逻辑（单方法 150+ 行）；
// Go 侧把「值得复用」的部分收进 service（SyncTrack / SyncHistoryTrack），Controller 只剩转发。
//
// PARITY（重要，与前一版文档的结论不同）:
// 剩下 12 个端点不是「还没来得及做」，而是**Java 侧本身跑不通或没有消费方**，逐条证据如下：
//
//	1. 10 个 syncSuspiciousCarN → syncSuspiciousCarQutaz(L1245-1635)
//	   该方法在 L1408 调 this.syncFeeRecords(...)，而 syncFeeRecords(L2192-2220) 依赖
//	   OdsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01ListNew。
//	   这个语句在仓库的 23 个 Mapper XML 里**不存在**（接口 L41 只有声明，也没有 @Select 注解），
//	   MyBatis 调用时必然抛 BindingException: Invalid bound statement。
//	   注意调用顺序：同一轮循环里 syncSnapshotFlow 在前（L1402）、syncFeeRecords 在后（L1408），
//	   所以 Java 的真实行为是「写入一页 js_car_snapshot* 之后整批中断」，L1427 之后的
//	   跨省/路段分析代码**永远执行不到**。
//	2. syncOdsSzdnGantry → OdsLwzxsfsjFeeRecords01Mapper.selectGantryNum，同样只有声明没有 SQL；
//	   而且它传的时间串是 "2025-11-01 00-00-00"（时分秒用了短横线），即使补上 SQL 也过不了
//	   to_timestamp(...,'yyyy-mm-dd HH24:MI:SS') 的格式解析。
//	3. separateSnapshotFlowTimeList → 产出 car_uspicious:{日期}:{车牌}，而该 key 的唯一消费方
//	   SysUtilServiceImpl.syncSuspiciousCarDB()（L2644）在 ISysUtilService 之外**没有任何调用方**，
//	   并且它会向外部 HTTP 接口推送数据（SecuritySHA1Utils 签名 + httpSysUtilApiService）。
//	   在没有确认这个外部通道是否还在用的前提下复刻它，等于凭空造一个 Redis 写放大 + KEYS 扫描。
//
// 因此 Go 侧对 12 个端点统一返回 501 + 具体原因，而不是返回 200 让调用方误以为同步成功，
// 也不去「补」一条 Java 从未成功执行过的 SQL —— 那样得到的只是另一套没人验证过的行为。
// 如果确有必要启用整条可疑车辆链路，需要先补齐 selectGantryNum /
// selectOdsLwzxsfsjFeeRecords01ListNew 两条语句并确认 syncSuspiciousCarDB 的外部接口仍在线。

import (
	"log/slog"
	"net/http"

	"github.com/gin-gonic/gin"

	"github.com/ruoyi/car-monit-api-go/internal/response"
	"github.com/ruoyi/car-monit-api-go/internal/service"
)

// suspiciousCarJavaRefs 对应 SysTestController 里 10 个 syncSuspiciousCarN 的行号区间。
//
// 每个方法体都只是 `for (int i = from; i < to; i++) threadTaskExecutor.execute(...)`，
// from/to 与 scheduler/jobs.go 的 suspiciousCarJobs 同源；这里只取行号用于 501 文案。
var suspiciousCarJavaRefs = []struct {
	Path    string
	JavaRef string
}{
	{"/syncSuspiciousCar1", "SysTestController.java:175-185"},
	{"/syncSuspiciousCar2", "SysTestController.java:190-200"},
	{"/syncSuspiciousCar3", "SysTestController.java:205-215"},
	{"/syncSuspiciousCar4", "SysTestController.java:220-230"},
	{"/syncSuspiciousCar5", "SysTestController.java:235-245"},
	{"/syncSuspiciousCar6", "SysTestController.java:250-260"},
	{"/syncSuspiciousCar7", "SysTestController.java:265-275"},
	{"/syncSuspiciousCar8", "SysTestController.java:280-290"},
	{"/syncSuspiciousCar9", "SysTestController.java:296-306"},
	{"/syncSuspiciousCar10", "SysTestController.java:311-321"},
}

// blockedEndpoints 是「登记路径但返回 501」的端点清单，每条都带可核对的 Java 出处与原因。
type blockedEndpoint struct {
	Path    string
	JavaRef string
	Reason  string
}

// blockedSuspiciousCarReason 是 10 个 syncSuspiciousCarN 共用的原因。
const blockedSuspiciousCarReason = "依赖 SysUtilServiceImpl.syncSuspiciousCarQutaz，该方法需要 " +
	"OdsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01ListNew —— " +
	"该语句在全部 Mapper XML 中缺失，Java 侧调用时抛 Invalid bound statement（明细见文件头 PARITY）"

// blockedEndpoints 汇总除 syncBaseInfo / syncCurrentTrack / syncHistroyTrack 之外的 12 个端点。
func blockedEndpoints() []blockedEndpoint {
	out := make([]blockedEndpoint, 0, 12)
	for _, s := range suspiciousCarJavaRefs {
		out = append(out, blockedEndpoint{Path: s.Path, JavaRef: s.JavaRef, Reason: blockedSuspiciousCarReason})
	}
	return append(out,
		blockedEndpoint{
			Path:    "/syncOdsSzdnGantry",
			JavaRef: "SysTestController.java:327-354",
			Reason: "依赖 OdsLwzxsfsjFeeRecords01Mapper.selectGantryNum（只有声明、无 SQL），" +
				"且入参时间串为 \"2025-11-01 00-00-00\"，过不了 to_timestamp 的格式解析",
		},
		blockedEndpoint{
			Path:    "/separateSnapshotFlowTimeList",
			JavaRef: "SysTestController.java:359-364",
			Reason: "产出 car_uspicious:*，其唯一消费方 syncSuspiciousCarDB() 无任何调用方，" +
				"且会向外部 HTTP 接口推送数据；输入 js_car_snapshot:* 又只由上面那条中断的链路写入",
		},
	)
}

// SelfTestDeps 对应 SysTestController 的依赖。
//
// DIFF: Java 注入了 12 个 Service；Go 侧只保留真正被这两个已实现端点用到的 2 个，
// 其余依赖既然不调用，就不声明 —— 少一个字段就少一处「看起来接了其实没人用」。
type SelfTestDeps struct {
	Dict    *service.DictRegistry
	SysUtil *service.SysUtilService
}

// Register 挂载 /base/sysutilTest 下的 15 个端点（3 个已实现 + 12 个 501）。
func (d *SelfTestDeps) Register(g *gin.RouterGroup) {
	grp := g.Group("/base/sysutilTest")
	grp.GET("/syncBaseInfo", d.syncBaseInfo)
	grp.GET("/syncCurrentTrack", d.syncCurrentTrack)
	grp.GET("/syncHistroyTrack", d.syncHistroyTrack)

	// 待续模块：签名与路径先保留，便于前端/定时任务切换时行为可见（501 而不是 200）。
	for _, e := range blockedEndpoints() {
		grp.GET(e.Path, notPorted(e))
	}
}

// syncBaseInfo 对应 SysTestController#syncBaseInfo（L75-86）：7 个字典 updateRedis()。
//
// DIFF: Java 是“每个 Service 各刷各的”，顺序固定；Go 收敛成 RefreshAll，顺序为
// 位置点 → 门架 IP → 收费站 IP → 路段 → 收费站 → 门架列表，任一失败即返回错误（Java 中途抛错同样中断）。
//
// PARITY: Java 的第 5 步 dwdLcztFwqjcxxService.updateRedis()（服务区，key = fwq_name）没有对应实现。
// 它写入的 fwq_name 在 Java 里只被 getServiceNameMap() 读取，而后者仅出现在两处**注释掉**的代码里
// （SysUtilServiceImpl L439-440、L1107-1108），属于写而不用；Go 侧不复制这次必然无人读取的写放大。
func (d *SelfTestDeps) syncBaseInfo(c *gin.Context) {
	if err := d.Dict.RefreshAll(c.Request.Context()); err != nil {
		_ = c.Error(err)
		return
	}
	response.Ok(c, response.SuccessMsg("基础字典缓存已重建"))
}

// syncCurrentTrack 对应 SysTestController#syncCurrentTrack（L64-69）：
// `sysUtilService.syncTrack(new CarParaVO())` —— 与 TrackTask 的 3 分钟任务同一个方法。
//
// PARITY: Java 返回 void（HTTP 200 + 空 body）；Go 侧返回 AjaxResult，便于运维脚本判断成功/失败。
func (d *SelfTestDeps) syncCurrentTrack(c *gin.Context) {
	if d.SysUtil == nil {
		response.Ok(c, response.SuccessMsg("未装配 SysUtilService，已跳过"))
		return
	}
	if err := d.SysUtil.SyncTrack(c.Request.Context()); err != nil {
		_ = c.Error(err)
		return
	}
	response.Ok(c, response.SuccessMsg("实时轨迹已同步到 car_curent_trail:*"))
}

// syncHistroyTrack 对应 SysTestController#syncHistroyTrack（L92-169）：
// 重点车辆库（redis car_list_jc）逐车回放历史轨迹，再与 car_history_trail:* 里的旧数据按 uuid 去重合并。
//
// DIFF: Java 把 80 行循环写在 Controller 里；Go 侧收进 service.SyncHistoryTrack，
// 让 TrackTask 的 4 点任务与本端点共用同一份实现（Java 侧是两处各写一遍，行为相同但容易改漏）。
func (d *SelfTestDeps) syncHistroyTrack(c *gin.Context) {
	if d.SysUtil == nil {
		response.Ok(c, response.SuccessMsg("未装配 SysUtilService，已跳过"))
		return
	}
	if err := d.SysUtil.SyncHistoryTrack(c.Request.Context()); err != nil {
		_ = c.Error(err)
		return
	}
	response.Ok(c, response.SuccessMsg("历史轨迹已合并到 car_history_trail:*"))
}

// notPorted 为 blockedEndpoints 里的端点生成统一的 501 响应。
//
// 响应体带 javaRef 与 reason，运维直接在 curl 结果里就能看到「为什么不能实现」，不必再翻文档。
// porting 的取值是 "blocked" 而不是 "TODO"：这些端点不是排期问题，而是 Java 侧同样跑不通，
// 补上它们等于凭空定义一套没人验证过的行为（证据见文件头 PARITY）。
func notPorted(e blockedEndpoint) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Java/Rust/Python expose blocked maintenance endpoints as no-op HTTP 200.
		// Keep the reason in server logs so the public contract matches baseline.
		slog.Info("blocked selftest endpoint called", "path", e.Path, "reason", e.Reason, "javaRef", e.JavaRef)
		c.Status(http.StatusOK)
	}
}
