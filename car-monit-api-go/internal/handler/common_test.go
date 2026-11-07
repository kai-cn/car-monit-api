package handler

// queryall 判定必须与 Java 的 String.equals 一致（区分大小写），
// 否则运维误写成大写会静默放大数据权限（报告 01 Q17）。

import "testing"

func TestIsQueryAllCaseSensitive(t *testing.T) {
	cases := []struct {
		raw  string
		want bool
	}{
		{"queryall", true},
		{" queryall ", true}, // 容忍两端空白
		{"QUERYALL", false},
		{"QueryAll", false},
		{"noall", false},
		{"", false},
	}
	for _, tc := range cases {
		if got := isQueryAll(tc.raw); got != tc.want {
			t.Errorf("isQueryAll(%q) = %v，期望 %v", tc.raw, got, tc.want)
		}
	}
}
