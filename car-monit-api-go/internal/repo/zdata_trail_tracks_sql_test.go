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
	return s
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
func TestCarNoAndCarNoListAreIndependentAnds(t *testing.T) {
	src := mustSource(t, "zdata_trail_tracks.go")
	if strings.Contains(src, "} else if utils.IsNotBlank(vo.CarNo)") {
		t.Error("carNo 又退回 if/else 分支了：carNo 与 carNoList 应当是两个独立的 AND 条件")
	}
	for _, frag := range []string{
		`if utils.IsNotBlank(vo.CarNo) {`,
		`tx.Where("envehicleid = ?", vo.CarNo)`,
		`if len(vo.CarNoList) > 0 {`,
		`tx.Where("envehicleid IN ?", vo.CarNoList)`,
	} {
		if !strings.Contains(src, frag) {
			t.Errorf("缺少 %s", frag)
		}
	}
}

// TestCallerOrderBeatsRepoOrder：gorm 的 Order 追加，先加入的优先级高。
func TestCallerOrderBeatsRepoOrder(t *testing.T) {
	src := mustSource(t, "ods_rt_szdn_snapshot_flow_addcode.go")
	caller := strings.Index(src, "ApplyOrder(ctx, tx)")
	own := strings.Index(src, `tx.Order("snapshottime desc")`)
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
