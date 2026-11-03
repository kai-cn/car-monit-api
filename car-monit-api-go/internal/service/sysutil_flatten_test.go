package service

// flattenCarNoList 是 total 与行集共用的一套车牌条件（CarTrackQueryNew / CarTrackCountNew
// 都调它）。它的两条性质决定 P-PAGE-8 的修复会不会又变成"两边各数各的"：
//   - 空车牌要丢掉（Java 是 stream().map(getCarNo)，但 CommonUtil.isNotBlank 那层过滤在
//     carTrackQueryNew 里，留着空串会让 IN(...) 里多一个空元素）；
//   - Carlist 为空时不能动 CarNoList —— count 与取数是两次调用，第二次若把列表清空，
//     total 就会来自无车牌条件的全表计数。

import (
	"testing"

	"github.com/ruoyi/car-monit-api-go/internal/model"
)

func TestFlattenCarNoList(t *testing.T) {
	cases := []struct {
		name string
		in   []model.CarVO
		pre  []string // 调用前已有的 CarNoList
		want []string
	}{
		{"拍平并丢掉空车牌", []model.CarVO{{CarNo: "粤A1"}, {CarNo: ""}, {CarNo: "  "}, {CarNo: "粤B2"}},
			nil, []string{"粤A1", "粤B2"}},
		{"Carlist 为空则保持原 CarNoList", nil, []string{"粤X9"}, []string{"粤X9"}},
		{"Carlist 全空车牌则得到空列表（覆盖 pre）", []model.CarVO{{CarNo: ""}}, []string{"粤X9"}, []string{}},
	}
	for _, tc := range cases {
		vo := &model.CarParaVO{Carlist: tc.in, CarNoList: tc.pre}
		flattenCarNoList(vo)
		if len(vo.CarNoList) != len(tc.want) {
			t.Errorf("%s: 得 %q, 期望 %q", tc.name, vo.CarNoList, tc.want)
			continue
		}
		for i := range tc.want {
			if vo.CarNoList[i] != tc.want[i] {
				t.Errorf("%s[%d]: 得 %q, 期望 %q", tc.name, i, vo.CarNoList[i], tc.want[i])
			}
		}
	}
}

// TestFlattenCarNoListIsIdempotent：count 与取数会在同一个 vo 上各调一次，
// 第二次必须得到与第一次相同的结果，否则 total 和行集用的不是同一批车牌。
func TestFlattenCarNoListIsIdempotent(t *testing.T) {
	vo := &model.CarParaVO{Carlist: []model.CarVO{{CarNo: "粤A1"}, {CarNo: ""}, {CarNo: "粤B2"}}}
	flattenCarNoList(vo)
	first := append([]string(nil), vo.CarNoList...)
	flattenCarNoList(vo)
	if len(vo.CarNoList) != len(first) {
		t.Fatalf("第二次调用改变了 CarNoList: %q → %q", first, vo.CarNoList)
	}
	for i := range first {
		if vo.CarNoList[i] != first[i] {
			t.Fatalf("第二次调用改变了 CarNoList[%d]: %q → %q", i, first[i], vo.CarNoList[i])
		}
	}
}
