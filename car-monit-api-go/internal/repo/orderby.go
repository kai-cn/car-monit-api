package repo

// JAVA 对照:
//
//	pro-base-common/src/main/java/com/ruoyi/common/core/page/PageDomain.java:96-103（getOrderBy）
//	pro-base-common/src/main/java/com/ruoyi/common/utils/PageUtils.java:23-25（escapeOrderBySql + PageHelper.orderBy）
//	pro-base-common/src/main/java/com/ruoyi/common/utils/sql/SqlUtil.java:31-42（白名单校验）
//
// 类/职责: 把调用方通过 orderByColumn/isAsc 指定的排序，带到 19 张基础表的 List 查询里
// 对应 Go 文件: internal/repo/orderby.go
//
// 为什么走 context 而不是给 List 加一个参数：22 个 Repo 都有 List(ctx, q, limit)，
// 加参数要同时改 interface、22 个实现和 service 里的调用点，任何一处漏改都是静默的行为漂移。
// ctx 已经是这些方法的第一个参数且 db.ORM(ctx) 本就在用它，代价只是一个请求级取值。
//
// DIFF: PageHelper 的 orderBy 是「在 SQL 后追加 ORDER BY」，与 Repo 里写死的顺序谁优先，
// 取决于追加的先后。这里在 Repo 施加自身 Order **之前**取用调用方排序，
// 让调用方显式请求的排序优先 —— 与 Java「调用方传了 orderByColumn 就按它排」的意图一致。
//
// PARITY: 空排序（绝大多数请求）完全不改现有行为，因此本轮之前的所有排序结论继续成立。

import (
	"context"
	"strings"

	"gorm.io/gorm"
)

type orderByKey struct{}

// OrderClause 是已校验的 ORDER BY 片段，例如 "agent_pk desc"。
// 由 handler 层构造（那里才知道 HTTP 参数与 400 语义），Repo 只负责施加。
type OrderClause struct{ SQL string }

// WithOrder 把排序片段放进请求上下文。空片段时原样返回，避免给每个查询加无谓的取值。
func WithOrder(ctx context.Context, clause string) context.Context {
	if strings.TrimSpace(clause) == "" {
		return ctx
	}
	return context.WithValue(ctx, orderByKey{}, OrderClause{SQL: clause})
}

// OrderFrom 取出上下文里的排序片段，没有则空串。
func OrderFrom(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	if v, ok := ctx.Value(orderByKey{}).(OrderClause); ok {
		return v.SQL
	}
	return ""
}

// ApplyOrder 把调用方排序附加到查询上。
//
// 调用方排序已在 handler 层过白名单（见 handler.orderByClause），这里不再校验，
// 但保留一次空值短路：绝大多数请求不带排序参数，不应产生任何额外开销。
func ApplyOrder(ctx context.Context, tx *gorm.DB) *gorm.DB {
	clause := OrderFrom(ctx)
	if clause == "" {
		return tx
	}
	return tx.Order(clause)
}
