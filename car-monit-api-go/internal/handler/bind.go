package handler

// JAVA 对照: pro-base-common/src/main/java/com/ruoyi/common/core/controller/BaseController.java:60-140
//           （startPage() / getDataTable() 读 pageNum·pageSize·orderByColumn）
//           + Spring MVC 的方法参数绑定（WebDataBinder 把 query/form 参数写进 Controller 形参）
// 类/职责: HTTP 入参绑定与分页参数解析 —— 取代 Spring 的"方法参数自动绑定"
// 对应 Go 文件: internal/handler/bind.go
// 关键映射:
//   Controller 形参 `(OdsSzdnGantry q)`  → bindQuery(c, &q)
//   startPage() 读 pageNum/pageSize      → pageParams(c)
//   PageHelper 注入的 LIMIT/OFFSET       → Offset()/PageSize（见 crud.go 的切片补偿）
//
// DIFF: gin 默认按 `form` tag（没有则按字段名）绑定 query；Java 前端传的字段名是 camelCase，
// 而实体上的同名信息存在 json tag 里。为了不给 22 个模型补 form tag（加错一个就静默失效），
// 这里按 json tag 反射绑定 —— 参数名与 Java 完全一致，前端零改动。
//
// PARITY: 参数名匹配同时尝试 json tag 原样、首字母大写、小写三种写法，
// 因为 RuoYi 前端偶有 `bigId` / `BigId` / `bigid` 混用。

import (
	"errors"
	"fmt"
	"reflect"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/ruoyi/car-monit-api-go/internal/middleware"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

// errSilentSkip 表示"这个参数按没传处理"，不是错误。
//
// 实测 Java 对不同字段类型的非法值处理并不统一，必须分别对齐：
//
//	字段类型     请求值            Java 行为
//	Integer    ?type=abc        HTTP 400（BindException）
//	String     ?uuid=abc         HTTP 200，按字面值过滤（查不到 → total=0）
//	Date       ?enterTime=abc    HTTP 200，字段保持 null，等于没有这个过滤条件
//
// 日期这条最容易写错：直觉上该和 Integer 一样回 400，但 Java 不会 ——
// 它没给 java.util.Date 注册 form 转换器，解析不了就留空。
// 若 Go 在这里报错，会把 Java 能正常返回全量的请求变成 400。
var errSilentSkip = errors.New("按未传处理")

// bindQuery 把 query / form 参数写进 dest（必须是指向结构体的指针）。
//
// 支持的字段类型：string / 数字 / bool 及其指针、time.Time / model.Day /
// model.DateTime / model.Timestamp 及其指针、[]string（逗号分隔）。
//
// PARITY（本轮修正）：解析失败不再一律静默忽略。此前 Go 把所有绑定错误都丢掉，
// 等于"这个过滤条件没传"，于是返回一个**更大**的结果集却报 200，调用方无从察觉。
// 现在按 Java 的真实行为分三类：
//   - 数字类型解析失败 → 400（与 Java 的 BindException 一致）；
//   - 日期类型解析失败 → 跳过（errSilentSkip，与 Java 一致）；
//   - 绑定器不支持的字段类型（结构体 / map / 非字符串切片）→ 跳过。
func bindQuery(c *gin.Context, dest any) error {
	v := reflect.ValueOf(dest)
	if v.Kind() != reflect.Ptr || v.IsNil() {
		return nil
	}
	v = v.Elem()
	if v.Kind() != reflect.Struct {
		return nil
	}
	t := v.Type()
	for i := 0; i < t.NumField(); i++ {
		f := t.Field(i)
		if f.PkgPath != "" { // 未导出字段
			continue
		}
		name := jsonName(f)
		if name == "" || name == "-" {
			continue
		}
		raw, ok := lookupParam(c, name)
		if !ok || raw == "" {
			continue
		}
		if !supportsType(f.Type) {
			// 结构体 / map / *DateTime 这类绑定器不支持的字段：Java 侧同样绑不上
			// （实测 provcapture?tailcapturetime=… 时 Java 既没报错也没过滤），
			// 所以按「没传这个条件」处理。已在校验报告记为 P-FILT-3。
			continue
		}
		if err := setByString(v.Field(i), raw); err != nil {
			if errors.Is(err, errSilentSkip) {
				continue // 与 Java 一致：解析不了的日期就当没传这个条件
			}
			return middleware.NewBindError(400,
				"Failed to convert '"+name+"', rejected value ["+raw+"].", err)
		}
	}
	return nil
}

// supportsType 判断字段类型能否由字符串绑定。
//
// 必须在调用 setByString **之前**判：setByString 处理指针时会先分配再递归，
// 如果等到递归失败才发现不支持，字段就已经变成一个「非 nil 的零值」，
// 于是这条过滤条件会带着零值进 WHERE —— 比忽略参数更糟。
func supportsType(t reflect.Type) bool {
	switch t {
	case reflect.TypeOf(time.Time{}), reflect.TypeOf(model.Day{}),
		reflect.TypeOf(model.DateTime{}), reflect.TypeOf(model.Timestamp{}):
		return true
	}
	switch t.Kind() {
	case reflect.String,
		reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64,
		reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64,
		reflect.Float32, reflect.Float64, reflect.Bool:
		return true
	case reflect.Slice:
		return t.Elem().Kind() == reflect.String
	case reflect.Ptr:
		return supportsType(t.Elem())
	}
	return false
}

// jsonName 取 json tag 的第一段，没有 tag 时退化为字段名。
func jsonName(f reflect.StructField) string {
	tag := f.Tag.Get("json")
	if tag == "" {
		return f.Name
	}
	if idx := strings.Index(tag, ","); idx >= 0 {
		tag = tag[:idx]
	}
	if tag == "-" {
		return ""
	}
	return tag
}

// lookupParam 依次尝试 json 名、首字母大写、全小写三种写法。
func lookupParam(c *gin.Context, name string) (string, bool) {
	candidates := []string{name, strings.ToUpper(name[:1]) + name[1:], strings.ToLower(name)}
	for _, key := range candidates {
		if val, ok := c.GetQuery(key); ok {
			return val, true
		}
		if val := c.PostForm(key); val != "" {
			return val, true
		}
	}
	return "", false
}

// setByString 把一个字符串写进字段，尽量宽容（解析失败按"忽略"处理）。
func setByString(field reflect.Value, raw string) error {
	if !field.CanSet() {
		return fmt.Errorf("字段不可设置")
	}
	raw = strings.TrimSpace(raw)

	// 指针：先在临时值上试解析，成功后才替换原字段。
	// 直接在原字段上 New 再递归的话，一旦递归失败，字段就变成"非 nil 的零值"，
	// 过滤条件会带着 0001-01-01 / 0 进 SQL —— 比忽略参数更错（两处单测都抓到过这个）。
	if field.Kind() == reflect.Ptr {
		if !field.CanSet() {
			return fmt.Errorf("字段不可设置")
		}
		tmp := reflect.New(field.Type().Elem())
		if err := setByString(tmp.Elem(), raw); err != nil {
			return err
		}
		field.Set(tmp)
		return nil
	}

	switch field.Type() {
	case reflect.TypeOf(time.Time{}), reflect.TypeOf(model.Day{}),
		reflect.TypeOf(model.DateTime{}), reflect.TypeOf(model.Timestamp{}):
		// 实体里的日期列（Java 的 java.util.Date / java.sql.Timestamp）统一按 Java 绑定器的
		// 实际能力解析；解析不了就保持字段为 nil，即「没有这个过滤条件」。
		return bindDateString(field, raw)
	}

	switch field.Kind() {
	case reflect.String:
		field.SetString(raw)
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		n, err := strconv.ParseInt(raw, 10, 64)
		if err != nil {
			return err
		}
		field.SetInt(n)
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		n, err := strconv.ParseUint(raw, 10, 64)
		if err != nil {
			return err
		}
		field.SetUint(n)
	case reflect.Float32, reflect.Float64:
		f, err := strconv.ParseFloat(raw, 64)
		if err != nil {
			return err
		}
		field.SetFloat(f)
	case reflect.Bool:
		b, err := strconv.ParseBool(raw)
		if err != nil {
			return err
		}
		field.SetBool(b)
	case reflect.Slice:
		// supportsType 已保证元素是 string；这里只兜住直接调用 setByString 的新代码
		if field.Type().Elem().Kind() != reflect.String {
			return fmt.Errorf("不支持的切片元素类型 %s", field.Type().Elem())
		}
		parts := strings.Split(raw, ",")
		out := reflect.MakeSlice(field.Type(), 0, len(parts))
		for _, p := range parts {
			if p = strings.TrimSpace(p); p != "" {
				out = reflect.Append(out, reflect.ValueOf(p))
			}
		}
		field.Set(out)
	default:
		return fmt.Errorf("不支持的字段类型 %s", field.Type())
	}
	return nil
}

// paramDateLayouts 是 Java 侧**请求参数绑定**真正接受的日期格式集合。
//
// 实测方法：对 :9902 打 /base/trailtracks/list?enterTime=<值>，
// 用 total 是否变化判断该值有没有被绑成 Date（未绑定 → 不过滤 → total 仍是全量 1379）。
//
//	入参                                       Java total   结论
//	2025-09-10                                 0            接受
//	2025-09-10 12:39:49                        17           接受
//	2025-09-10 12:39                           0            接受
//	2025/09/10                                 0            接受
//	2025-09-10T12:39:49                        1379         拒绝
//	2025-09-10T12:39:49.000+08:00              1379         拒绝
//	2025-09-10T12:39:49Z                       1379         拒绝
//	2025-09-10 12:39:49.123                    1379         拒绝（带毫秒也不行）
//	1757479189000 / 1757479189                 1379         拒绝（epoch 不行）
//	Sep 10 2025 / not-a-date                   1379         拒绝
//
// 这组行为符合 Spring 走 java.util.Date 字符串构造（Date.parse）的解析能力：
// 认横线/斜杠日期和空格分隔的时间，认不了 ISO 的 'T'、毫秒与时区偏移。
//
// DIFF: model.ParseTime 支持 8 种格式 + epoch 毫秒，是为「查询串解析」设计的，
// 用在参数绑定上会比 Java 宽容得多 —— 实测把它接进去以后，
// feeGantry?createtime=<ISO> 与 provcapture?tailcapturetime=<ISO> 两处
// Java 不过滤（返回全量）而 Go 过滤（返回 0 行），凭空造出差异。绑定必须走这个窄集合。
var paramDateLayouts = []string{
	"2006-01-02",
	"2006-01-02 15:04:05",
	"2006-01-02 15:04",
	"2006/01/02",
	"2006/01/02 15:04:05",
}

// parseParamDate 按 Java 绑定器的实际能力解析日期参数；解析不了就返回 errSilentSkip。
func parseParamDate(raw string) (time.Time, error) {
	s := strings.TrimSpace(raw)
	for _, layout := range paramDateLayouts {
		t, err := time.ParseInLocation(layout, s, time.Local)
		if err != nil {
			continue
		}
		// Go 的 time.Parse 允许在秒后面多出一段小数（"2025-09-10 12:39:49.123" 能过），
		// Java 的 Date.parse 不行。用「反向格式化必须与输入逐字相同」把多出来的尾巴挡掉。
		if t.Format(layout) != s {
			continue
		}
		return t, nil
	}
	return time.Time{}, fmt.Errorf("Java 的日期参数绑定不接受该值 %q: %w", raw, errSilentSkip)
}

// bindDateString 把 raw 写进 dest（dest 的静态类型必须是 time.Time / Day / DateTime / Timestamp）。
//
// PARITY: 解析失败时保持字段原值（未赋值即 nil，Repo 据此不加条件），与 Java「绑不上就当没传」一致。
func bindDateString(dest reflect.Value, raw string) error {
	t, err := parseParamDate(raw)
	if err != nil {
		return err
	}
	if dest.Type() == reflect.TypeOf(time.Time{}) {
		dest.Set(reflect.ValueOf(t))
		return nil
	}
	dest.Set(reflect.ValueOf(t).Convert(dest.Type()))
	return nil
}

type PageParams struct {
	PageNum  int
	PageSize int
	// Reasonable 对应 PageDomain.reasonable（Java 默认 true）：页码越界时回夹到有效页。
	Reasonable bool
	// OrderBy 对应 PageDomain.getOrderBy() 经 SqlUtil.escapeOrderBySql 校验后的片段。
	// 空串表示调用方没要求排序。
	OrderBy string
	// OrderByErr 非 nil 表示调用方给了 orderByColumn 但取值过不了白名单。
	// Java 在这种情况下抛 UtilException 且无人 catch → HTTP 500；
	// Go 统一按「参数非法」回 400 —— 这是有意偏离，理由见 orderByClause。
	OrderByErr error
}

// Offset 对应 PageHelper 计算出的 SQL OFFSET
func (p PageParams) Offset() int {
	if p.PageNum <= 1 {
		return 0
	}
	return (p.PageNum - 1) * p.PageSize
}

// ClampToLastPage 复刻 PageHelper 的 reasonable：页码超过总页数时回夹到末页。
//
// 必须在拿到 COUNT 之后调用（Java 也是先 count 再 limit）。
// PageSize<=0 时不夹：那一页本来就是空集，Java 也一样不返回行。
func (p *PageParams) ClampToLastPage(total int64) {
	if !p.Reasonable || p.PageSize <= 0 || total <= 0 {
		return
	}
	pages := (total + int64(p.PageSize) - 1) / int64(p.PageSize)
	if int64(p.PageNum) > pages {
		p.PageNum = int(pages)
	}
}

// pageParams 对应 startPage()：RuoYi 的 PageDomain 默认 pageNum=1、pageSize=10。
//
// DIFF: Java 的 PageHelper 靠 ThreadLocal 把 limit/offset 塞给下一次 SQL；
// Go 只能显式取值再传给 Repo —— 好处是不会出现"忘了 startPage 就查全表"。
//
// PARITY（本轮修正的三条）：
//  1. pageSize 不再有 1000 的静默上限。Java 没有上限，Go 截断会让调用方少拿数据却毫无感知；
//     真要设上限也必须显式报错，而不是悄悄少给。
//  2. 显式传 0 或负数是「这一页不给行」，不是「回落默认值」。Java 就是这样。
//     注意 Repo 侧约定 limit<=0 表示「不加 LIMIT」，所以 pageSize=0 必须由调用方短路，
//     绝不能当成「查全表」（见 crud.go 的 handleList）。
//  3. orderByColumn/isAsc 生效（见 orderByClause），非法值报错而不是当没传。
func pageParams(c *gin.Context) PageParams {
	p := PageParams{PageNum: 1, PageSize: 10, Reasonable: true}
	// Java: Convert.toInt(getParameter(PAGE_NUM), 1) —— 缺失和非数字都回落默认值
	if n, err := strconv.Atoi(strings.TrimSpace(c.Query("pageNum"))); err == nil {
		p.PageNum = n
	}
	if n, err := strconv.Atoi(strings.TrimSpace(c.Query("pageSize"))); err == nil {
		p.PageSize = n
	}
	if p.PageNum < 1 {
		p.PageNum = 1
	}
	if p.PageSize < 0 {
		p.PageSize = 0
	}
	if v := strings.TrimSpace(c.Query("reasonable")); v != "" {
		if b, err := strconv.ParseBool(v); err == nil {
			p.Reasonable = b
		}
	}
	p.OrderBy, p.OrderByErr = orderByClause(c)
	return p
}

// orderByClause 对应 PageDomain.getOrderBy()（L33）+ SqlUtil.escapeOrderBySql()（L31-42）。
//
// Java 的拼法是 toUnderScoreCase(orderByColumn) + " " + isAsc，isAsc 默认 "asc"，
// 并兼容前端常发的 "ascending"/"descending"。
//
// DIFF（状态码）：Java 校验不通过就抛 UtilException，19 个 base Controller 没有 try/catch、
// 全仓也没有 @ControllerAdvice，于是回 HTTP 500。Go 回 400 —— 语义上「你传的排序列不合法」
// 属于请求错误，且 Go 已有 BindError 专门复刻 Spring 的参数转换错误体。
// 这是本轮唯一一处「明知与 Java 不同、但仍然选择更正确行为」的分页改动，已记入校验报告。
func orderByClause(c *gin.Context) (string, error) {
	col := strings.TrimSpace(c.Query("orderByColumn"))
	if col == "" {
		return "", nil
	}
	dir := strings.TrimSpace(c.Query("isAsc"))
	switch strings.ToLower(dir) {
	case "":
		dir = "asc"
	case "ascending":
		dir = "asc"
	case "descending":
		dir = "desc"
	}
	clause := utils.ToUnderScoreCase(col) + " " + dir
	if len(clause) > orderByMaxLen {
		return "", middleware.NewBindError(400,
			"Failed to convert 'orderByColumn', rejected value ["+col+"]. orderBy 已超过最大限制", nil)
	}
	if !validOrderBy(clause) {
		return "", middleware.NewBindError(400,
			"Failed to convert 'orderByColumn', rejected value ["+col+"]. 参数不符合规范，不能进行查询", nil)
	}
	return clause, nil
}

const orderByMaxLen = 500 // SqlUtil.ORDER_BY_MAX_LENGTH

// orderByItem 是单个排序项：列名（可带表名/别名前缀）+ 可选 ASC/DESC。
var orderByItem = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?((\s+(ASC|DESC))?)$`)

// validOrderBy 比 Java 的字符白名单（SqlUtil.SQL_PATTERN = "[a-zA-Z0-9_\ \,\.]+"）更严：
// Java 只挡引号/分号/注释符，Go 这里要求每一项都能解析成「列名 [ASC|DESC]」，
// 逗号分隔的多列允许（Java 也允许），从而不依赖调用方的自律就把 ORDER BY 注入面关掉。
func validOrderBy(clause string) bool {
	for _, item := range strings.Split(clause, ",") {
		item = strings.TrimSpace(strings.ToUpper(item))
		if item == "" {
			return false
		}
		if !orderByItem.MatchString(item) {
			return false
		}
	}
	return true
}
