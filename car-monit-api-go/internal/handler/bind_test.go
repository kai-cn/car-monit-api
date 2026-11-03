package handler

// 覆盖本轮修正的分页/排序/绑定语义。这些用例不需要数据库，
// 因为要验的恰恰是「参数怎么被解释」，而不是「查回来什么」。

import (
	"errors"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/ruoyi/car-monit-api-go/internal/model"
)

func ctxWithQuery(raw string) *gin.Context {
	gin.SetMode(gin.TestMode)
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	c.Request = httptest.NewRequest("GET", "/base/gantry/list?"+raw, nil)
	return c
}

func TestPageParamsPageSize(t *testing.T) {
	cases := []struct {
		name  string
		query string
		want  int
	}{
		{"缺省", "", 10},
		{"非数字回落默认", "pageSize=abc", 10},
		{"显式 0 就是 0 行", "pageSize=0", 0},
		{"负数当 0", "pageSize=-1", 0},
		{"大页不再被截到 1000", "pageSize=5000", 5000},
		{"刚好 1000", "pageSize=1000", 1000},
	}
	for _, tc := range cases {
		if got := pageParams(ctxWithQuery(tc.query)).PageSize; got != tc.want {
			t.Errorf("%s: pageSize=%d, 期望 %d (query=%q)", tc.name, got, tc.want, tc.query)
		}
	}
}

func TestPageParamsPageNum(t *testing.T) {
	if got := pageParams(ctxWithQuery("")).PageNum; got != 1 {
		t.Errorf("缺省 pageNum=%d, 期望 1", got)
	}
	if got := pageParams(ctxWithQuery("pageNum=0")).PageNum; got != 1 {
		t.Errorf("pageNum=0 应归一到 1, 实得 %d", got)
	}
	if got := pageParams(ctxWithQuery("pageNum=abc")).PageNum; got != 1 {
		t.Errorf("pageNum 非数字应回落 1, 实得 %d", got)
	}
}

func TestClampToLastPage(t *testing.T) {
	// Java 的 PageDomain.reasonable 默认 true：越界回夹末页
	p := pageParams(ctxWithQuery("pageNum=99999&pageSize=5"))
	p.ClampToLastPage(1526)
	if p.PageNum != 306 {
		t.Errorf("越界应回夹到末页 306, 实得 %d", p.PageNum)
	}
	if p.Offset() != 1525 {
		t.Errorf("末页 offset 应为 1525, 实得 %d", p.Offset())
	}

	// 显式 reasonable=false 时不夹
	p2 := pageParams(ctxWithQuery("pageNum=99999&pageSize=5&reasonable=false"))
	p2.ClampToLastPage(1526)
	if p2.PageNum != 99999 {
		t.Errorf("reasonable=false 不应回夹, 实得 %d", p2.PageNum)
	}

	// pageSize=0 不夹（那一页本来就是空集）
	p3 := pageParams(ctxWithQuery("pageNum=99999&pageSize=0"))
	p3.ClampToLastPage(1526)
	if p3.PageNum != 99999 {
		t.Errorf("pageSize=0 时不应回夹, 实得 %d", p3.PageNum)
	}

	// total=0 不夹，避免页码被算成 0
	p4 := pageParams(ctxWithQuery("pageNum=3&pageSize=10"))
	p4.ClampToLastPage(0)
	if p4.PageNum != 3 {
		t.Errorf("total=0 时页码应保持, 实得 %d", p4.PageNum)
	}
}

func TestOrderByClause(t *testing.T) {
	cases := []struct{ query, want string }{
		{"", ""},
		{"orderByColumn=agentPk&isAsc=desc", "agent_pk desc"},
		{"orderByColumn=agentPk", "agent_pk asc"}, // PageDomain.isAsc 默认 asc
		{"orderByColumn=gantryCode&isAsc=descending", "gantry_code desc"},
		{"orderByColumn=gantryCode&isAsc=ascending", "gantry_code asc"},
		{"orderByColumn=id,agentPk&isAsc=desc", "id,agent_pk desc"}, // 与 Java 一致：整串一起转下划线
	}
	for _, tc := range cases {
		got, err := orderByClause(ctxWithQuery(tc.query))
		if err != nil {
			t.Errorf("%q 不该报错: %v", tc.query, err)
			continue
		}
		if got != tc.want {
			t.Errorf("%q → %q, 期望 %q", tc.query, got, tc.want)
		}
	}
}

func TestOrderByClauseRejectsInjection(t *testing.T) {
	// Java 靠 SqlUtil 白名单挡这些（抛 UtilException → HTTP 500）；Go 回 400。
	// 用 %3B 而不是裸分号：Go 的 ParseQuery 会把裸分号当分隔符丢弃，编码后才测得到「值里带分号」。
	for _, q := range []string{
		"orderByColumn=uuid%3Bdrop&isAsc=desc",
		"orderByColumn=a&isAsc=asc--",
		"orderByColumn=name&isAsc=asc/*",
		"orderByColumn='x'&isAsc=desc",
		"orderByColumn=" + strings.Repeat("a", 600) + "&isAsc=desc",
	} {
		if got, err := orderByClause(ctxWithQuery(q)); err == nil {
			t.Errorf("%q 应被拒绝, 实得 %q", q, got)
		}
	}
}

func TestBindQueryTypeMismatchIsError(t *testing.T) {
	// endTime 在 Java 与 Go 都是 Integer；传时间串在 Java 是 400，Go 不能再静默忽略
	var vo model.CarParaVO
	err := bindQuery(ctxWithQuery("endTime=2025-10-02+00:00:00"), &vo)
	if err == nil {
		t.Fatal("endTime 传非整数应报错，而不是当作没传")
	}
	if !strings.Contains(err.Error(), "endTime") {
		t.Errorf("错误里应指出是哪个参数: %v", err)
	}
}

func TestBindQueryNormalFields(t *testing.T) {
	var vo model.CarParaVO
	if err := bindQuery(ctxWithQuery("carNo=赣AF12345&flag=bannian&pageSize=20&pageNum=2"), &vo); err != nil {
		t.Fatalf("正常参数不该报错: %v", err)
	}
	if vo.CarNo != "赣AF12345" || vo.Flag != "bannian" || vo.PageSize == nil || *vo.PageSize != 20 {
		t.Errorf("绑定结果不符: %+v", vo)
	}
}

// TestBindParamFailureSemantics 锁住实测到的 Java 三分类：
//
//	Integer 非法值 → 400   (?type=abc / ?pointCount=abc，实测 :9902 都是 400)
//	String  任意值 → 200   (?uuid=abc 按字面过滤，实测 total=0)
//	Date    非法值 → 200   (?enterTime=not-a-date 字段留 null、不过滤，实测 total=1379)
//	Date    合法值 → 生效  (?enterTime=2025-09-10 04:39:49 实测 total=0)
//
// 日期这一类以前要么全忽略（丢条件）、要么全报错（把好请求打成 400），两种都不对。
func TestBindParamFailureSemantics(t *testing.T) {
	var tr model.ZdataTrailTracks
	if err := bindQuery(ctxWithQuery("enterTime=not-a-date&plateKey=赣A"), &tr); err != nil {
		t.Errorf("非法日期应按没传处理，不该报错: %v", err)
	}
	if tr.EnterTime != nil {
		t.Errorf("非法日期不该写入字段: %+v", tr.EnterTime)
	}
	if tr.PlateKey == nil || *tr.PlateKey != "赣A" {
		t.Errorf("同一请求里的其它参数不该被牵连: %+v", tr.PlateKey)
	}

	var ok model.ZdataTrailTracks
	if err := bindQuery(ctxWithQuery("enterTime=2025-09-10+04:39:49"), &ok); err != nil {
		t.Errorf("合法日期不该报错: %v", err)
	}
	if ok.EnterTime == nil {
		t.Error("合法日期必须绑定成功，否则过滤条件会丢失（P-FILT-3）")
	}

	for _, q := range []string{"type=abc", "pointCount=abc"} {
		var bad model.ZdataTrailTracks
		if err := bindQuery(ctxWithQuery(q), &bad); err == nil {
			t.Errorf("%q 应回 400（Java 对 Integer 字段就是这样）", q)
		}
	}
}

// TestParseParamDateMatchesJava 锁住实测到的 Java 日期参数绑定能力矩阵
// （判据：/base/trailtracks/list?enterTime=… 的 total 是否变化，见 paramDateLayouts 注释表）。
// Go 的 model.ParseTime 支持 8 种格式 + epoch，比 Java 宽得多；
// 绑定必须用窄集合，否则 Java 不过滤（返回全量）而 Go 过滤（返回 0 行）。
func TestParseParamDateMatchesJava(t *testing.T) {
	slash := string(rune('/'))
	accepted := []string{
		"2025-09-10",
		"2025-09-10 12:39:49",
		"2025-09-10 12:39",
		"2025" + slash + "09" + slash + "10",
		"2025" + slash + "09" + slash + "10 12:39:49",
	}
	rejected := []string{
		"2025-09-10T12:39:49",           // ISO 的 T：Java 不认
		"2025-09-10T12:39:49.000+08:00", // 真实 trailPoints 里的形状
		"2025-09-10T12:39:49Z",
		"2025-09-10 12:39:49.123", // 带毫秒也不行
		"1757479189000",           // epoch 毫秒
		"1757479189",              // epoch 秒
		"Sep 10 2025",
		"not-a-date",
		"2025-13-45T99:99:99",
	}
	for _, v := range accepted {
		if _, err := parseParamDate(v); err != nil {
			t.Errorf("Java 接受 %q，Go 却拒绝: %v", v, err)
		}
	}
	for _, v := range rejected {
		_, err := parseParamDate(v)
		if err == nil {
			t.Errorf("Java 拒绝 %q，Go 却接受 —— 会凭空加出一个过滤条件", v)
			continue
		}
		if !errors.Is(err, errSilentSkip) {
			t.Errorf("%q 的错误必须是 errSilentSkip（按没传处理），实得 %v", v, err)
		}
	}
}

func TestPageParamsOrderByIsSilentWhenAbsent(t *testing.T) {
	p := pageParams(ctxWithQuery("pageSize=5"))
	if p.OrderBy != "" || p.OrderByErr != nil {
		t.Errorf("未传排序参数时 OrderBy 应为空, 实得 %q err=%v", p.OrderBy, p.OrderByErr)
	}
}
