package repo

// SQL 层断言。internal/repo 此前没有任何单测，而本轮有四个修复**只在生成的 SQL 里可见**，
// 且当前数据状态下无法从 HTTP 响应观察差异（carTrackQueryByCarNo 因 flag=bannian 恒返回 0 行，
// 2025 年的数据全在窗口外），所以只能靠源码文本断言把结论钉住，防止以后被"顺手优化"掉。
//
// 覆盖：
//   P-TRK-3 历史轨迹投影必须是 Java XML 的那 20 列（少 15 列 → 2162 个字段恒 null）
//   P-TRK-4 bannian / yiyue 必须是双边时间窗（Java 有 `extime <= now()`）
//   P-FILT-5 carNo 与 carNoList 必须是两个独立条件的 AND（Java 是两个 <if>）
//   P-PAGE-4 调用方排序必须加在 Repo 自身 Order 之前（gorm 的 Order 是追加，先加的优先）

import (
	"os"
	"strings"
	"testing"
)

// 断言依赖"同目录源码文本"，因此只能在 go test 的包目录下运行；用 t.Fatal 明确提示，
// 免得文件移动后这些断言静默失效。
func repoSource(name string) (string, error) {
	b, err := os.ReadFile(name)
	return string(b), err
}

func mustSource(t *testing.T, name string) string {
	t.Helper()
	s, err := repoSource(name)
	if err != nil {
		t.Fatalf("读不到 %s（本文件的断言依赖同目录源码）: %v", name, err)
	}
	// 本仓库 core.autocrlf=true，Windows 检出的源码是 CRLF；
	// 不归一化的话下面按行切的断言会在别人机器上假失败/假通过。
	return strings.ReplaceAll(s, "\r\n", "\n")
}

// TestHistoryTrailProjectionMatchesJavaXML 对应 ZdataTrailTracksMapper.xml:117-136。
func TestHistoryTrailProjectionMatchesJavaXML(t *testing.T) {
	want := []string{
		"cid AS uuid", "envehicleid AS plate_key",
		"enaxlecount", "entolllaneid", "entollstationid", "entollstationname",
		"envehicleclass", "envehicleid", "envehicletype", "enweight",
		"entime AS enter_time", "extime AS exit_time",
		"extolllaneid", "extollstationid", "extollstationname",
		"exvehicleclass", "exvehicleid", "exvehicletype", "exweight",
		"trailpoints AS trail_points",
	}
	var missing []string
	for _, c := range want {
		if !strings.Contains(historyTrailColumns, c) {
			missing = append(missing, c)
		}
	}
	if len(missing) > 0 {
		t.Errorf("投影缺列：%v\n（Java 的 getHistoryTrail 投 20 列；少一列就是一个字段在 Go 恒为 null）", missing)
	}
}

// TestHistoryTrailRowCoversProjection 保证投影结构体与列常量同步：
// 加了列忘了加字段，GORM 会静默丢弃该列。
func TestHistoryTrailRowCoversProjection(t *testing.T) {
	src := mustSource(t, "zdata_trail_tracks.go")
	body, ok := substringBetween(src, "type historyTrailRow struct {", "\n}")
	if !ok {
		t.Fatal("找不到 historyTrailRow 定义")
	}
	for _, col := range []string{
		"uuid", "plate_key", "enter_time", "exit_time", "trail_points",
		"enaxlecount", "entolllaneid", "entollstationid", "entollstationname",
		"envehicleclass", "envehicleid", "envehicletype", "enweight",
		"extolllaneid", "extollstationid", "extollstationname",
		"exvehicleclass", "exvehicleid", "exvehicletype", "exweight",
	} {
		if !strings.Contains(body, `column:`+col+`"`) {
			t.Errorf("historyTrailRow 缺 gorm 列 %s，投影会静默丢字段", col)
		}
	}
}

// TestRelativeWindowsAreBounded 对应 XML:144-150 的双边条件。
func TestRelativeWindowsAreBounded(t *testing.T) {
	src := mustSource(t, "zdata_trail_tracks.go")
	for _, tc := range []struct{ flag, lower, caseBody string }{
		{"bannian", `tx.Where("extime >= now() - 180")`, `case "bannian":`},
		{"yiyue", `tx.Where("extime >= now() - 3")`, `case "yiyue":`},
	} {
		i := strings.Index(src, tc.caseBody)
		if i < 0 {
			t.Fatalf("找不到 %s 分支", tc.flag)
		}
		line, _, _ := strings.Cut(src[i:], "\n")
		nextLine, _, _ := strings.Cut(src[i+len(line)+1:], "\n")
		if !strings.Contains(nextLine, tc.lower) {
			t.Errorf("%s 分支缺少下界 %s，实得 %q", tc.flag, tc.lower, nextLine)
		}
		if !strings.Contains(nextLine, `extime <= now()`) {
			t.Errorf("%s 分支缺上界 extime <= now()（Java XML 是双边窗口），实得 %q", tc.flag, nextLine)
		}
	}
}

// TestCarNoAndCarNoListAreIndependentAnds：Go 曾写成 if/else if，
// 等于"传了 carNoList 就忽略 carNo"，两条件同时给出时结果集会偏大。
//
// 断言锁在谓词构建函数体内、且检查两个 if 之间有没有 else：
// 早先版本只在全文件里 grep 一个固定串 `} else if utils.IsNotBlank(vo.CarNo)`，
// 而真实的回退写法是 `} else if len(vo.CarNoList) > 0 {`，那种改法 grep 不到，
// 测试会在 bug 存在的情况下照样通过（本轮复核实测复现过）。
func TestCarNoAndCarNoListAreIndependentAnds(t *testing.T) {
	src := mustSource(t, "zdata_trail_tracks.go")
	body, ok := substringBetween(src, "func applyHistoryTrailFilters(", "\n}")
	if !ok {
		t.Fatal("找不到 applyHistoryTrailFilters（getHistoryTrail 的谓词应集中在这里）")
	}
	const carNoIf = `if utils.IsNotBlank(vo.CarNo) {`
	const carNoListIf = `if len(vo.CarNoList) > 0 {`
	for _, frag := range []string{
		carNoIf, `tx.Where("envehicleid = ?", vo.CarNo)`,
		carNoListIf, `tx.Where("envehicleid IN ?", vo.CarNoList)`,
	} {
		if !strings.Contains(body, frag) {
			t.Errorf("applyHistoryTrailFilters 缺少 %s", frag)
		}
	}
	i, j := strings.Index(body, carNoIf), strings.Index(body, carNoListIf)
	if i < 0 || j < 0 {
		return // 片段缺失已由上面的 Errorf 报过，这里不再做下标运算
	}

	first, second := carNoIf, carNoListIf
	if j < i {
		first, second = carNoListIf, carNoIf
	}
	gap := body[strings.Index(body, first):strings.Index(body, second)]
	if strings.Contains(gap, "else") {
		t.Errorf("carNo 与 carNoList 被 else 连成了互斥分支，应为两个独立 AND；实得 %q", gap)
	}
	// 第二个 if 必须紧跟第一个 if 的收尾 `}`，中间不能夹别的条件。
	before := strings.TrimRight(body[:strings.Index(body, second)], " \t\n")
	if !strings.HasSuffix(before, "}") {
		t.Errorf("第二个过滤条件不是紧跟在 `}` 之后的独立 if 语句，实得结尾 %q",
			before[max(0, len(before)-60):])
	}
}

// TestCountAndRowsSharePredicates：轨迹的 total 与行集必须出自同一套 WHERE。
//
// Java 那边这是天然的 —— PageHelper 用原 SQL 生成 count；Go 一旦让 CountHistoryTrail
// 自己抄一份条件，两边就会各自演化，而 total 与数据"各说各话"比原来的
// total=页大小（P-PAGE-8）更难被发现。
func TestCountAndRowsSharePredicates(t *testing.T) {
	src := mustSource(t, "zdata_trail_tracks.go")
	for _, fn := range []string{"GetHistoryTrail", "CountHistoryTrail"} {
		body, ok := substringBetween(src,
			"func (r *ZdataTrailTracksRepo) "+fn+"(", "\n}")
		if !ok {
			t.Fatalf("找不到 %s", fn)
		}
		if !strings.Contains(body, "applyHistoryTrailFilters(") {
			t.Errorf("%s 没有走 applyHistoryTrailFilters，谓词会出现两份", fn)
		}
	}
	countBody, _ := substringBetween(src,
		"func (r *ZdataTrailTracksRepo) CountHistoryTrail(", "\n}")
	if strings.Contains(countBody, ".Limit(") {
		t.Error("CountHistoryTrail 带了 LIMIT —— total 会退化成页大小")
	}
	if !strings.Contains(countBody, ".Count(&") {
		t.Error("CountHistoryTrail 没有走 .Count，拿不到 PageHelper 语义的 total")
	}
}

// TestCallerOrderBeatsRepoOrder：gorm 的 Order 追加，先加入的优先级高。
func TestCallerOrderBeatsRepoOrder(t *testing.T) {
	src := mustSource(t, "ods_rt_szdn_snapshot_flow_addcode.go")
	body, ok := substringBetween(src,
		"func (r *OdsRtSzdnSnapshotFlowAddcodeRepo) List(", "\n}")
	if !ok {
		t.Fatal("找不到 List 函数体（断言依赖同目录源码）")
	}
	caller := strings.Index(body, "ApplyOrder(ctx, tx)")
	own := strings.Index(body, `tx.Order("snapshottime desc")`)
	if caller < 0 || own < 0 {
		t.Fatalf("片段缺失：ApplyOrder=%d snapshottime desc=%d", caller, own)
	}
	if caller > own {
		t.Error("ApplyOrder 必须排在自身 Order 之前，否则调用方的 orderByColumn 会被 snapshottime desc 压住")
	}
}

func substringBetween(s, left, right string) (string, bool) {
	i := strings.Index(s, left)
	if i < 0 {
		return "", false
	}
	rest := s[i+len(left):]
	j := strings.Index(rest, right)
	if j < 0 {
		return "", false
	}
	return rest[:j], true
}
