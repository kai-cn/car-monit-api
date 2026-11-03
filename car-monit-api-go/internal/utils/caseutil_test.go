package utils

// Java 的 StringUtils.toUnderScoreCase 有两个反直觉分支，锁住它们，
// 防止以后有人"顺手优化"成常见驼峰转换实现而改变了数据库列名。

import "testing"

func TestToUnderScoreCase(t *testing.T) {
	cases := []struct{ in, want string }{
		{"", ""},
		{"agentPk", "agent_pk"},
		{"gantryCode", "gantry_code"},
		{"id", "id"},
		{"ID", "id"},          // 首字符 preUpper 被显式置 false，且末位不更新 nextUpper
		{"IDCard", "id_card"}, // 连续大写只在"后面接到小写"时切一次
		{"HTTPStatus", "http_status"},
		{"plateKey", "plate_key"},
		{"bigId", "big_id"},
		{"a", "a"},
		{"pointCount", "point_count"},
	}
	for _, tc := range cases {
		if got := ToUnderScoreCase(tc.in); got != tc.want {
			t.Errorf("ToUnderScoreCase(%q)=%q, 期望 %q", tc.in, got, tc.want)
		}
	}
}
