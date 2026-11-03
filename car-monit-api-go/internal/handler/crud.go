package handler

// JAVA 对照:
//
//	pro-base-common/src/main/java/com/ruoyi/common/core/controller/BaseController.java:60-140（startPage/getDataTable）
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnGantryController.java:29-53（list/getInfo/listAll 三件套）
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsLwzxsfsjFeeRecords01Controller.java:46-204
//	  （列表返回前用门架字典回填 2 列、listToExport 直接返回 List）
//	pro-business-api/src/main/java/com/ruoyi/base/controller/OdsRtSzdnSnapshotFlowAddcodeController.java:40-142
//
// 类/职责: 把 19 个"基础表只读 CRUD"Controller 收敛成一份可复用的注册器
// 对应 Go 文件: internal/handler/crud.go
// 关键映射:
//
//	@GetMapping("/list")       public TableDataInfo list(T q)     → grp.GET("/list")
//	@GetMapping("/{id}")       public AjaxResult getInfo(id)      → grp.GET("/:id")（IDParam 决定变量名）
//	@GetMapping("/listAll")    public List<T> getListAll()        → grp.GET("/listAll")
//	@GetMapping("/listToExport") public List<T> listToExport(q)   → grp.GET("/listToExport")
//	startPage() + selectXList(q)                                  → pageParams + Count（切片补偿 OFFSET）
//	getDataTable(list)                                           → response.OkTable
//
// DIFF: Java 每个 Controller 都抄一遍"startPage(); service.selectList(q); return getDataTable(list);"，
// Go 用泛型注册器写一次 —— 19 个 Controller 变成 19 行注册语句，新增表不会漏写 total。
//
// DIFF: PageHelper 的 LIMIT/OFFSET 是隐式注入的；Repo 的 List 只接受 limit，所以这里取
// "offset+pageSize" 行再切片，等价于 SQL 的 LIMIT n OFFSET m（代价是偏移量大时多传几行，可忽略）。
//
// PARITY: getInfo 在 Java 里 null 时 Spring 会写出「空响应体 + 200」，Go 用 c.Status(200) 复刻；
// 而 AjaxResult.success(null) 则会省略 data 键（见 response.Success）。

import (
	"context"
	"net/http"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"

	"github.com/ruoyi/car-monit-api-go/internal/middleware"
	"github.com/ruoyi/car-monit-api-go/internal/repo"
	"github.com/ruoyi/car-monit-api-go/internal/response"
)

// entityRepo 是「主键为字符串」的 Repo 契约（19 张表里的 17 张）。
//
// DIFF: Java 靠 BaseMapper<T> 的接口默认方法免写 CRUD；Go 没有默认方法，只能把用到的
// 5 个方法显式列进接口，由 Repo 实现满足（编译期校验，漏一个就编译不过）。
type entityRepo[T any] interface {
	List(ctx context.Context, q *T, limit int) ([]T, error)
	Count(ctx context.Context, q *T) (int64, error)
	GetByID(ctx context.Context, id string) (*T, error)
	ListAll(ctx context.Context) ([]T, error)
}

// entityRepoNumericID 适用于主键是 bigint 的两张表（gantry_ip / toll_station_ip）。
//
// PARITY: Java 的 @PathVariable Long id 遇到 "abc" 由 Spring 抛 400；Go 侧在 access 里显式
// 解析并返回同语义的 400（见 accessOfNumeric）。
type entityRepoNumericID[T any] interface {
	List(ctx context.Context, q *T, limit int) ([]T, error)
	Count(ctx context.Context, q *T) (int64, error)
	GetByID(ctx context.Context, id int64) (*T, error)
	ListAll(ctx context.Context) ([]T, error)
}

// access 把 Repo 的读操作抽成函数值，屏蔽 GetByID 的 id 类型差异。
type access[T any] struct {
	list    func(ctx context.Context, q *T, limit int) ([]T, error)
	count   func(ctx context.Context, q *T) (int64, error)
	getByID func(ctx context.Context, id string) (*T, error)
	all     func(ctx context.Context) ([]T, error)
}

func accessOf[T any](r entityRepo[T]) *access[T] {
	return &access[T]{list: r.List, count: r.Count, getByID: r.GetByID, all: r.ListAll}
}

func accessOfNumeric[T any](r entityRepoNumericID[T]) *access[T] {
	return &access[T]{
		list:  r.List,
		count: r.Count,
		all:   r.ListAll,
		getByID: func(ctx context.Context, id string) (*T, error) {
			n, err := strconv.ParseInt(strings.TrimSpace(id), 10, 64)
			if err != nil {
				// 这是 Spring 的参数转换失败（HTTP 400 + 默认错误体），不是业务异常。
				return nil, middleware.NewBindError(400, "Failed to convert 'id', rejected value ["+id+"].", err)
			}
			return r.GetByID(ctx, n)
		},
	}
}

// ReadOnlySpec 描述一个基础表 Controller 的路由形态。
type ReadOnlySpec[T any] struct {
	// Base 对应 @RequestMapping 的值，如 "/base/gantry"
	Base string
	// IDParam 对应 @PathVariable("id") 里的变量名；空时取 Base 最后一段
	IDParam string
	// FlatInfo 为 true 时 /{id} 直接返回实体（Java: `public T getInfo(...)` 而不是 AjaxResult）
	FlatInfo bool
	// NumericID 为 true 时，Java 侧签的是 @PathVariable("bigId") Long xxx，
	// 非数字的 path 变量在 Spring 就变成 TypeMismatch 而回到 HTTP 400。
	// 用标志而不是另开一个 Numeric 注册器：这三张表的 big_id 在库里是文本列，
	// Repo.GetByID 必须继续吃 string，只为了校验而把接口改成 int64 会适得其反。
	NumericID bool
	// AllowAll 对应 /listAll（全量，无分页、无包装）
	AllowAll bool
	// AllowExport 对应 /listToExport（分页但不包装成 TableDataInfo）
	AllowExport bool
	// Prepare 在查询前加工查询条件，对应 Controller 里 setXxx 的那几行
	Prepare func(ctx context.Context, q *T) error
	// Decorate 在返回前加工结果行，对应 `for (T r : list) { ... }`
	Decorate func(ctx context.Context, rows []T) error
	// DecorateExport 是 /listToExport 专用的加工函数（不填则用 Decorate）。
	// 存在的理由：Java 的 list 与 listToExport 各抄了一份循环，其中有细微差异
	// （如 snapshotflow 的 list 会重写图片域名，listToExport 不会）。
	DecorateExport func(ctx context.Context, rows []T) error
}

// RegisterReadOnly 注册"主键是字符串"的基础表 Controller。
func RegisterReadOnly[T any](g *gin.RouterGroup, spec ReadOnlySpec[T], r entityRepo[T]) {
	registerReadOnly(g, spec, accessOf(r))
}

// RegisterReadOnlyNumeric 注册"主键是 bigint"的基础表 Controller。
func RegisterReadOnlyNumeric[T any](g *gin.RouterGroup, spec ReadOnlySpec[T], r entityRepoNumericID[T]) {
	registerReadOnly(g, spec, accessOfNumeric(r))
}

// registerReadOnly 是两种主键类型的公共装配逻辑。
func registerReadOnly[T any](g *gin.RouterGroup, spec ReadOnlySpec[T], a *access[T]) {
	grp := g.Group(spec.Base)
	idParam := spec.IDParam
	if idParam == "" {
		idParam = lastSegment(spec.Base)
	}

	grp.GET("/list", func(c *gin.Context) {
		var q T
		if err := bindQuery(c, &q); err != nil {
			_ = c.Error(err)
			return
		}
		handleList(c, spec, a, &q)
	})
	if spec.AllowExport {
		grp.GET("/listToExport", func(c *gin.Context) {
			var q T
			if err := bindQuery(c, &q); err != nil {
				_ = c.Error(err)
				return
			}
			handleExport(c, spec, a, &q)
		})
	}
	if spec.AllowAll {
		grp.GET("/listAll", func(c *gin.Context) { handleListAll(c, a) })
	}
	// 注意：gin 允许 "/list" 与 "/:id" 同级共存（静态段优先），因此路径与 Java 完全一致。
	grp.GET("/:"+idParam, func(c *gin.Context) { handleInfo(c, spec, a, idParam) })
}

// handleList 对应 `startPage(); List<T> list = service.selectList(q); return getDataTable(list);`
//
// PARITY: PageHelper 的实际顺序是「先 COUNT、再按 reasonable 修正页码、最后 LIMIT」，
// Go 也必须先 count —— 否则拿不到总页数，就没法复刻「页码越界回夹末页」。
//
// PARITY: pageSize<=0 时不查库、直接给空 rows。
// Repo 约定 limit<=0 表示「不加 LIMIT 条件」，若把 pageSize=0 换算成 limit=0 传下去，
// 就会从「返回 0 行」变成「全表扫描」，方向完全相反。
func handleList[T any](c *gin.Context, spec ReadOnlySpec[T], a *access[T], q *T) {
	ctx := c.Request.Context()
	p := pageParams(c)
	if p.OrderByErr != nil {
		_ = c.Error(p.OrderByErr)
		return
	}
	if spec.Prepare != nil {
		if err := spec.Prepare(ctx, q); err != nil {
			_ = c.Error(err)
			return
		}
	}
	total, err := a.count(ctx, q)
	if err != nil {
		_ = c.Error(err)
		return
	}
	p.ClampToLastPage(total)

	rows := make([]T, 0)
	if p.PageSize > 0 {
		rows, err = a.list(repo.WithOrder(ctx, p.OrderBy), q, p.Offset()+p.PageSize)
		if err != nil {
			_ = c.Error(err)
			return
		}
		rows = pageSlice(rows, p)
		if spec.Decorate != nil {
			if err := spec.Decorate(ctx, rows); err != nil {
				_ = c.Error(err)
				return
			}
		}
	}
	response.OkTable(c, rows, total)
}

// handleExport 对应 `listToExport`：同样分页（Java 也调了 startPage），但不包 TableDataInfo。
func handleExport[T any](c *gin.Context, spec ReadOnlySpec[T], a *access[T], q *T) {
	ctx := c.Request.Context()
	p := pageParams(c)
	if p.OrderByErr != nil {
		_ = c.Error(p.OrderByErr)
		return
	}
	if spec.Prepare != nil {
		if err := spec.Prepare(ctx, q); err != nil {
			_ = c.Error(err)
			return
		}
	}
	// Java 的 PageHelper 在这条路径上同样会先算一次 COUNT（用于 reasonable），
	// 只是不把 total 放进响应体。
	total, err := a.count(ctx, q)
	if err != nil {
		_ = c.Error(err)
		return
	}
	p.ClampToLastPage(total)

	rows := make([]T, 0)
	if p.PageSize > 0 {
		rows, err = a.list(repo.WithOrder(ctx, p.OrderBy), q, p.Offset()+p.PageSize)
		if err != nil {
			_ = c.Error(err)
			return
		}
		rows = pageSlice(rows, p)
	}
	decorate := spec.DecorateExport
	if decorate == nil {
		decorate = spec.Decorate
	}
	if decorate != nil {
		if err := decorate(ctx, rows); err != nil {
			_ = c.Error(err)
			return
		}
	}
	c.JSON(http.StatusOK, rows)
}

// handleInfo 对应 `return AjaxResult.success(service.selectXById(id))` / `return entity`
func handleInfo[T any](c *gin.Context, spec ReadOnlySpec[T], a *access[T], idParam string) {
	id := c.Param(idParam)
	if spec.NumericID {
		// 对应 Spring 的 Long 参数转换：失败就是 HTTP 400，不会进方法体。
		if _, err := strconv.ParseInt(strings.TrimSpace(id), 10, 64); err != nil {
			_ = c.Error(middleware.NewBindError(400,
				"Failed to convert '"+idParam+"', rejected value ["+id+"].", err))
			return
		}
	}
	obj, err := a.getByID(c.Request.Context(), id)
	if err != nil {
		_ = c.Error(err)
		return
	}
	if spec.FlatInfo {
		if obj == nil {
			// PARITY: Spring 的做法是「不写响应体」，不是写 "null"
			c.Status(http.StatusOK)
			return
		}
		c.JSON(http.StatusOK, obj)
		return
	}
	response.OkData(c, obj)
}

// handleListAll 对应 `return service.selectXListAll()`：裸数组，不包装、不分页。
func handleListAll[T any](c *gin.Context, a *access[T]) {
	rows, err := a.all(c.Request.Context())
	if err != nil {
		_ = c.Error(err)
		return
	}
	if rows == nil {
		rows = make([]T, 0)
	}
	c.JSON(http.StatusOK, rows)
}

// pageSlice 等价于 SQL 的 OFFSET：列表已在 SQL 层限制了 offset+pageSize 行，这里切掉前 offset 行。
func pageSlice[T any](rows []T, p PageParams) []T {
	if rows == nil {
		return make([]T, 0)
	}
	if off := p.Offset(); off < len(rows) {
		return rows[off:]
	}
	return make([]T, 0)
}

// lastSegment 取 "/base/gantry" 的最后一段 "gantry"，作为默认的 @PathVariable 名。
func lastSegment(base string) string {
	idx := strings.LastIndex(base, "/")
	if idx < 0 || idx == len(base)-1 {
		return "id"
	}
	return base[idx+1:]
}
