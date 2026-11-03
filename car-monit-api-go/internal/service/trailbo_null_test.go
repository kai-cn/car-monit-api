package service

// P-SER-1 的三态语义测试：Java 的 String 有 null / "" / 有值 三种，Go 用 *string 表达。
// 这条边界完全靠 Java 源码与真实报文取证定下来（CommonUtil.isNull 返回空串、
// 裸 getter 返回 null），不是"看代码像"就能维持的，所以必须有可失败的测试。

import (
	"encoding/json"
	"testing"

	"github.com/ruoyi/car-monit-api-go/internal/model"
)

func TestJSONStrPtrMatchesFastjsonGetString(t *testing.T) {
	obj := map[string]json.RawMessage{
		"absent-null":  json.RawMessage("null"),
		"empty":        json.RawMessage(`""`),
		"value":        json.RawMessage(`"粤A1"`),
		"number":       json.RawMessage(`123`),
		"nested-nulls": json.RawMessage(`{"a":null}`),
	}

	if got := jsonStrPtr(obj, "missing"); got != nil {
		t.Errorf(`键不存在应得 null（fastjson getString 返回 null），实得 %q`, model.Val(got))
	}
	if got := jsonStrPtr(obj, "absent-null"); got != nil {
		t.Errorf(`值是 JSON null 应得 nil，实得 %q`, model.Val(got))
	}
	if got := jsonStrPtr(obj, "empty"); got == nil || *got != "" {
		t.Errorf(`值是 "" 必须保留空串（装箱非 nil），实得 %#v`, got)
	}
	if got := jsonStrPtr(obj, "value"); got == nil || *got != "粤A1" {
		t.Errorf(`普通字符串应原样取出，实得 %#v`, got)
	}
	// fastjson 的 getString 对数字取字面量，这里保持同一行为
	if got := jsonStrPtr(obj, "number"); got == nil || *got != "123" {
		t.Errorf(`数字应转成字面量字符串，实得 %#v`, got)
	}
}

// TestTrailBoJSONKeepsThreeStates 是这次改动的目的本身：编码必须能区分三种值。
func TestTrailBoJSONKeepsThreeStates(t *testing.T) {
	in := model.TrailBo{
		PointUuid:   nil,           // Java 未赋值 -> null
		ImagesArry:  model.Str(""), // Java setImagesArry("") -> ""（SysUtilServiceImpl.java:1198）
		Platenumber: model.Str("粤A12345"),
	}
	raw, err := json.Marshal(in)
	if err != nil {
		t.Fatal(err)
	}
	var got map[string]any
	if err := json.Unmarshal(raw, &got); err != nil {
		t.Fatal(err)
	}
	if v, ok := got["pointUuid"]; !ok || v != nil {
		t.Errorf(`pointUuid 应为 null，实得 %#v`, got["pointUuid"])
	}
	if v, ok := got["imagesArry"]; !ok || v != "" {
		t.Errorf(`imagesArry 应为 ""（合法空串，不能变成 null），实得 %#v`, got["imagesArry"])
	}
	if v := got["platenumber"]; v != "粤A12345" {
		t.Errorf(`platenumber 应为原值，实得 %#v`, v)
	}
}

// TrailInfo 既是出参也是入参（POST /base/sysutil/changeTrailInfo），
// 所以 null 与 "" 都要能吃进来且不吃瘪。
func TestTrailInfoJSONAcceptsNullAndEmpty(t *testing.T) {
	var a model.TrailInfo
	if err := json.Unmarshal([]byte(`{"trailUuid":null,"trailList":[{"imagesArry":""}]}`), &a); err != nil {
		t.Fatal(err)
	}
	if a.TrailUuid != nil {
		t.Errorf("trailUuid:null 应解成 nil，实得 %q", model.Val(a.TrailUuid))
	}
	if len(a.TrailList) != 1 || a.TrailList[0].ImagesArry == nil || *a.TrailList[0].ImagesArry != "" {
		t.Errorf(`imagesArry:"" 应保留空串，实得 %#v`, a.TrailList)
	}

	var b model.TrailInfo
	if err := json.Unmarshal([]byte(`{"trailUuid":"x"}`), &b); err != nil {
		t.Fatal(err)
	}
	if b.TrailUuid == nil || *b.TrailUuid != "x" {
		t.Errorf("有值时应装箱保留，实得 %#v", b.TrailUuid)
	}

	// 缺字段与显式 null 在 Java（Jackson）里都得到 null，Go 也必须一致
	var c model.TrailInfo
	if err := json.Unmarshal([]byte(`{}`), &c); err != nil {
		t.Fatal(err)
	}
	if c.TrailUuid != nil {
		t.Errorf("缺字段应得 nil，实得 %q", model.Val(c.TrailUuid))
	}
}
