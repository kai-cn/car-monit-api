package model

// 本文件不对应单个 Java 类，而是为「Java 的 String 可空」提供 Go 侧的等价写法。
//
// JAVA 对照: pro-base-common/src/main/java/com/ruoyi/common/utils/StringUtils.java
//           + org.apache.commons.lang3.StringUtils#isNotBlank
//           （MyBatis XML 里 <if test="x != null and x != ''"> 的判定语义）
// 对应 Go 文件: internal/model/nullstr.go
//
// 为什么需要这一组函数：
//
//	Java 实体字段是 String（引用类型），数据库 NULL 读进来就是 null，Jackson 输出 null。
//	Go 的 string 没有 null，pgx/GORM 会把 NULL 变成 ""，JSON 里就成了 ""，
//	两边永远对不上（首轮比对里这一类报了 7946 次）。所以可空列统一改成 *string。
//	改完之后，原来写 `q.X != ""` 的地方必须换成 NonEmpty(q.X)，取值的写 Val(q.X) ——
//	把指针语义收在这三个函数里，调用点读起来和改之前一样短。

// Val 返回 *string 的内容，nil 当空串。
//
// 对应 Java 的 Objects.toString(s, "")。用在「把实体字段交给只吃 string 的 API」时。
func Val(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

// NonEmpty 对应 MyBatis 的 <if test="x != null and x != ”">：nil 与空串都算“空”。
//
// 注意它不是 Java 的 isNotBlank：isNotBlank 还剪空白字符，这里保持与 XML 判定逐字一致。
func NonEmpty(s *string) bool {
	return s != nil && *s != ""
}

// Blank 是 NonEmpty 的反面，便于把 XML 里的 <if test="x == null or x == ”"> 写得更直白。
func Blank(s *string) bool { return !NonEmpty(s) }

// Str 把字面量装箱成 *string，用于构造测试数据和查询条件。
//
// DIFF: Java 直接写 setX("abc") 即可，Go 拿不到字面量的地址，必须过一层函数。
func Str(s string) *string { return &s }
