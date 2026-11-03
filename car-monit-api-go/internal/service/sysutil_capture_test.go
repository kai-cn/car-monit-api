package service

// 抓拍时间解析。这条路径的失败是静默的（err 被吞、captureTime 留空），
// 而下游 mapTrailBoList 的按时间去重/合并完全依赖它非空，所以必须有测试锁住。

import "testing"

func TestParseCaptureTime(t *testing.T) {
	cases := []struct {
		name, in string
		want     string // 期望 Format(layoutNormalTime) 结果；空串表示应解析失败
	}{
		// 真实轨迹点是这个形状：带毫秒和时区偏移
		{"带毫秒与时区", "2025-10-01T00:02:36.000+08:00", "2025-10-01 00:02:36"},
		{"干净格式", "2025-10-01T00:02:36", "2025-10-01 00:02:36"},
		{"带 Z 时区", "2025-10-01T00:02:36Z", "2025-10-01 00:02:36"},
		{"尾部有垃圾", "2025-10-01T00:02:36 extra", "2025-10-01 00:02:36"},
		{"太短应失败", "2025-10-01", ""},
		{"非法日期应失败", "2025-13-45T99:99:99", ""},
		{"空串应失败", "", ""},
	}
	for _, tc := range cases {
		got, ok := parseCaptureTime(tc.in)
		if tc.want == "" {
			if ok {
				t.Errorf("%s: %q 本应解析失败，实得 %v", tc.name, tc.in, got)
			}
			continue
		}
		if !ok {
			t.Errorf("%s: %q 解析失败（Java 的 SimpleDateFormat 能解析）", tc.name, tc.in)
			continue
		}
		if s := got.Format(layoutNormalTime); s != tc.want {
			t.Errorf("%s: %q → %q, 期望 %q", tc.name, tc.in, s, tc.want)
		}
	}
}
