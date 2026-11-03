// Package response 复刻 RuoYi 的统一响应壳，保证前端不需要改动。
//
// JAVA 对照:
//
//	pro-base-common/src/main/java/com/ruoyi/common/core/domain/AjaxResult.java:14-217
//	pro-base-common/src/main/java/com/ruoyi/common/core/page/TableDataInfo.java:11-85
//	pro-base-common/src/main/java/com/ruoyi/common/core/domain/R.java (泛型包装)
//	pro-base-common/src/main/java/com/ruoyi/common/constant/HttpStatus.java:8-94
//
// 对应 Go 文件: internal/response/response.go
//
// 关键映射:
//
//	AjaxResult extends HashMap<String,Object>  → map[string]any 的具名类型（字段顺序由 JSON 编码器决定，无语义影响）
//	AjaxResult.success(data)                  → response.Success(data)
//	BaseController.getDataTable(list)         → response.Table(list, total)
//	业务状态码 200/601/500                     → 常量 Success/Warn/Error（注意：这是响应体里的 code，不是 HTTP status）
package response

import (
	"net/http"
	"reflect"

	"github.com/gin-gonic/gin"
)

// isPresent 对应 StringUtils.isNotNull(Object)：只判 null，不判空。
//
// 为什么不能直接写 data != nil：Go 的 any 里装一个「类型化的空指针」
// （比如查不到记录时返回的 (*model.OdsSzdnTollStationIp)(nil)）时，data != nil 为真，
// 于是 Go 会输出 "data":null；而 Java 那边 object == null 成立，构造器直接把 data 这个键
// 省掉，输出 {"msg":...,"code":200}。实测 GET /base/tollStationIp/1（记号不存在）就是这样差一个键。
// 所以必须用 reflect 看指针本身是不是空。
//
// PARITY: RuoYi 用的是 isNotNull 而不是 isNotEmpty，空列表/空字符串仍然会带 data 键，
// 这里不能顺手把空集合也去掉。
func isPresent(data any) bool {
	if data == nil {
		return false
	}
	rv := reflect.ValueOf(data)
	switch rv.Kind() {
	case reflect.Ptr, reflect.Interface, reflect.Map, reflect.Slice, reflect.Func, reflect.Chan:
		return !rv.IsNil()
	}
	return true
}

// CodeSuccess 等业务状态码，对应 HttpStatus.java:13/93/83。
//
// DIFF: Java 里 `HttpStatus.SUCCESS` 与 `AjaxResult.success(...)` 分属两个类，天然不冲突；
// Go 同包内不允许「常量 Success」与「函数 Success」同名，故常量加 Code 前缀，
// 值保持一致（200/601/500），前端无需改动。
const (
	CodeSuccess = 200
	CodeWarn    = 601
	CodeError   = 500
)

// AjaxResult 对应 Java 的 AjaxResult。
//
// DIFF: Java 继承 HashMap，可以任意 put 额外键；Go 用 map 别名保留同样的动态性，
// 但类型是 map[string]any，取值时需要类型断言——这是"没有继承"的直接代价。
type AjaxResult map[string]any

// NewResult 对应 new AjaxResult(code, msg)
func NewResult(code int, msg string) AjaxResult {
	r := AjaxResult{"code": code, "msg": msg}
	return r
}

// Success 对应 AjaxResult.success()/success(data)/success(msg, data) 三个重载的合并。
// DIFF: Go 没有方法重载，Java 的三个静态方法在 Go 中用可变参数 + 判空表达。
func Success(data ...any) AjaxResult {
	r := NewResult(CodeSuccess, "操作成功")
	if len(data) > 0 && isPresent(data[0]) {
		r["data"] = data[0]
	}
	return r
}

// SuccessMsg 对应 AjaxResult.success(msg)
func SuccessMsg(msg string) AjaxResult { return NewResult(CodeSuccess, msg) }

// SuccessWith 对应 AjaxResult.success(msg, data)
func SuccessWith(msg string, data any) AjaxResult {
	r := NewResult(CodeSuccess, msg)
	if isPresent(data) {
		r["data"] = data
	}
	return r
}

// WarnMsg 对应 AjaxResult.warn(msg) / warn(msg, data)
func WarnMsg(msg string, data ...any) AjaxResult {
	r := NewResult(CodeWarn, msg)
	if len(data) > 0 && isPresent(data[0]) {
		r["data"] = data[0]
	}
	return r
}

// Fail 对应 AjaxResult.error() / error(msg) / error(msg, data)
func Fail(args ...any) AjaxResult {
	if len(args) == 0 {
		return NewResult(CodeError, "操作失败")
	}
	msg, _ := args[0].(string)
	r := NewResult(CodeError, msg)
	if len(args) > 1 && isPresent(args[1]) {
		r["data"] = args[1]
	}
	return r
}

// FailCode 对应 AjaxResult.error(code, msg)
func FailCode(code int, msg string) AjaxResult { return NewResult(code, msg) }

// Put 对应 AjaxResult.put(key, value) 的链式调用（Java 里返回 this）
func (r AjaxResult) Put(key string, value any) AjaxResult {
	r[key] = value
	return r
}

// IsSuccess 对应 AjaxResult.isSuccess()
func (r AjaxResult) IsSuccess() bool { return r["code"] == CodeSuccess }

// TableDataInfo 对应 TableDataInfo.java:11。JSON 键名 total/rows/code/msg 完全一致。
type TableDataInfo struct {
	Total int64  `json:"total"`
	Rows  any    `json:"rows"`
	Code  int    `json:"code"`
	Msg   string `json:"msg"`
}

// Table 对应 BaseController.getDataTable(List)：默认 code=200、msg=查询成功。
//
// DIFF: Java 用 PageHelper 的 PageInfo(list) 取 total（依赖 ThreadLocal 里的分页参数）；
// Go 没有隐式分页上下文，total 必须由调用方显式传入（通常是 COUNT 查询结果）。
func Table(rows any, total int64) TableDataInfo {
	return TableDataInfo{Total: total, Rows: rows, Code: CodeSuccess, Msg: "查询成功"}
}

// TableWithMsg 对应 Java 里 `tableData.setMsg("策略: " + strategy)` 这类改写。
func TableWithMsg(rows any, total int64, msg string) TableDataInfo {
	t := Table(rows, total)
	t.Msg = msg
	return t
}

// Ok 直接以 HTTP 200 返回 AjaxResult（对应 Spring 里 return AjaxResult 的行为）。
func Ok(c *gin.Context, r AjaxResult) {
	c.JSON(http.StatusOK, r)
}

// OkData 对应 BaseController.success(data)
func OkData(c *gin.Context, data any) {
	c.JSON(http.StatusOK, Success(data))
}

// OkTable 对应 return getDataTable(list)
func OkTable(c *gin.Context, rows any, total int64) {
	c.JSON(http.StatusOK, Table(rows, total))
}
