// Package es 是 Elasticsearch 访问层（纯 net/http 实现）。
//
// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/mq/config/ElasticsearchConfig.java
//   - com.ruoyi.base.service.optimization.EsIndexManageService
//   - com.ruoyi.mq.service.EsQueryService
//
// 对应 Go 文件: internal/es/client.go
//
// 关键映射:
//
//	RestHighLevelClient（elasticsearch-java） → 标准库 net/http + encoding/json
//	SearchRequest/BoolQueryBuilder           → 直接构造 ES DSL（map[string]any）
//	BulkProcessor（异步批量）                 → Client.Bulk（同步批量，由调用方控制并发）
//	scroll 上下文                            → Client.Scroll（显式 start/continue/clear）
//
// 架构决策（为什么不引第三方 ES SDK）:
//
//	官方 go-elasticsearch 版本必须与集群大版本严格匹配，而 GaussDB/ES 版本由运维侧决定；
//	本项目对 ES 的用法只有 4 个动作（search / count / bulk / scroll），
//	用 net/http 手写反而更稳、可测、零依赖。详见 README「架构决策」。
package es

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// Config 对应 application.yml:188-211
type Config struct {
	BaseURL      string
	Username     string
	Password     string
	ConnTimeout  time.Duration
	SocketTimout time.Duration
}

// Client 是 ES 门面。零值不可用，必须 New。
type Client struct {
	base string
	user string
	pass string
	http *http.Client
}

// New 构造客户端（不做连接检查：ES 属于可选依赖，允许启动时不可用）。
//
// DIFF: Java 用 @Bean 构造 RestHighLevelClient 并在启动期建立连接池；
// Go 的 http.Client 本身就是连接池，且本项目允许 ES 缺失（降级到 GaussDB），
// 因此 New 不 Ping，健康状态由 Client.Healthy 探测。
func New(cfg Config) *Client {
	connTimeout := cfg.ConnTimeout
	if connTimeout <= 0 {
		connTimeout = 30 * time.Second
	}
	socket := cfg.SocketTimout
	if socket <= 0 {
		socket = 30 * time.Second
	}
	return &Client{
		base: strings.TrimRight(cfg.BaseURL, "/"),
		user: cfg.Username,
		pass: cfg.Password,
		http: &http.Client{
			Timeout: socket,
			Transport: &http.Transport{
				MaxIdleConns:        100,
				MaxIdleConnsPerHost: 50,
				IdleConnTimeout:     90 * time.Second,
				// 建连超时（对应 Java 的 connection-timeout）
				TLSHandshakeTimeout:   connTimeout,
				ResponseHeaderTimeout: connTimeout,
			},
		},
	}
}

// Healthy 探测集群可用性（对应 isIndexHealthy / 健康检查端点）
func (c *Client) Healthy(ctx context.Context) bool {
	if c == nil || c.base == "" {
		return false
	}
	ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	req, err := c.newRequest(ctx, http.MethodGet, "/", nil)
	if err != nil {
		return false
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, resp.Body)
	return resp.StatusCode == http.StatusOK
}

// Search 执行 _search，返回原始 JSON（对应 EsQueryService 的 search 调用）。
//
// DIFF: Java 侧返回 SearchResponse/org.elasticsearch.search.SearchHit 强类型对象；
// Go 侧返回 map（schemaless），字段取值需要类型断言——ES 文档结构不受 schema 约束，
// 这里刻意不用结构体，避免每个索引都要维护一份 Go struct。
func (c *Client) Search(ctx context.Context, index string, body map[string]any) (map[string]any, error) {
	if c == nil {
		return nil, fmt.Errorf("es: 客户端未初始化")
	}
	raw, err := c.do(ctx, http.MethodPost, "/"+index+"/_search", body)
	if err != nil {
		return nil, err
	}
	var out map[string]any
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, fmt.Errorf("es search 响应解析失败: %w", err)
	}
	return out, nil
}

// Count 执行 _count（对应 GaussEsConsistencyService.countInEs）
func (c *Client) Count(ctx context.Context, index string, body map[string]any) (int64, error) {
	if c == nil {
		return 0, fmt.Errorf("es: 客户端未初始化")
	}
	raw, err := c.do(ctx, http.MethodPost, "/"+index+"/_count", body)
	if err != nil {
		return 0, err
	}
	var out struct {
		Count int64 `json:"count"`
	}
	if err := json.Unmarshal(raw, &out); err != nil {
		return 0, fmt.Errorf("es count 响应解析失败: %w", err)
	}
	return out.Count, nil
}

// Bulk 批量写入（对应 BulkProcessor.add + flush）。
// docs 里每一项是完整文档（含 _id 时用 {"_id": ...} 的形式包装见 BulkItem）。
func (c *Client) Bulk(ctx context.Context, index string, docs []map[string]any) error {
	if c == nil || len(docs) == 0 {
		return nil
	}
	var buf bytes.Buffer
	for _, d := range docs {
		meta := map[string]any{"index": map[string]any{"_index": index}}
		if id, ok := d["_id"]; ok {
			meta = map[string]any{"index": map[string]any{"_index": index, "_id": id}}
			delete(d, "_id")
		}
		b1, _ := json.Marshal(meta)
		b2, _ := json.Marshal(d)
		buf.Write(b1)
		buf.WriteByte('\n')
		buf.Write(b2)
		buf.WriteByte('\n')
	}
	raw, err := c.doRaw(ctx, http.MethodPost, "/_bulk", &buf, "application/x-ndjson")
	if err != nil {
		return err
	}
	var out struct {
		Errors bool `json:"errors"`
		Items  []map[string]struct {
			Status int `json:"status"`
			Error  any `json:"error"`
		} `json:"items"`
	}
	if err := json.Unmarshal(raw, &out); err != nil {
		return fmt.Errorf("es bulk 响应解析失败: %w", err)
	}
	if out.Errors {
		failed := 0
		for _, it := range out.Items {
			for _, v := range it {
				if v.Status >= 300 {
					failed++
				}
			}
		}
		return fmt.Errorf("es bulk 部分失败: %d 条", failed)
	}
	return nil
}

// ScrollPage 拉取一页 scroll 数据（对应 scroll 导出）。
// 返回 (本页文档, scrollId, 是否结束)。
func (c *Client) ScrollPage(ctx context.Context, index string, body map[string]any, keepalive string) ([]map[string]any, string, bool, error) {
	if keepalive == "" {
		keepalive = "5m"
	}
	path := "/" + index + "/_search?scroll=" + keepalive
	if body == nil {
		body = map[string]any{"size": 2000, "query": map[string]any{"match_all": map[string]any{}}}
	}
	raw, err := c.do(ctx, http.MethodPost, path, body)
	if err != nil {
		return nil, "", false, err
	}
	return parseHits(raw)
}

// ScrollNext 继续 scroll。
func (c *Client) ScrollNext(ctx context.Context, scrollID, keepalive string) ([]map[string]any, string, bool, error) {
	if keepalive == "" {
		keepalive = "5m"
	}
	raw, err := c.do(ctx, http.MethodPost, "/_search/scroll", map[string]any{
		"scroll":    keepalive,
		"scroll_id": scrollID,
	})
	if err != nil {
		return nil, "", false, err
	}
	return parseHits(raw)
}

// ClearScroll 释放 scroll 上下文（务必调用，否则 ES 会持有资源直到超时）。
//
// DIFF: Java 侧 SearchScrollRequest 由 SDK 管理生命周期；这里必须显式清理，属于"Go 里没有魔法"的典型点。
func (c *Client) ClearScroll(ctx context.Context, scrollID string) error {
	if scrollID == "" {
		return nil
	}
	_, err := c.do(ctx, http.MethodDelete, "/_search/scroll", map[string]any{"scroll_id": []string{scrollID}})
	return err
}

// CreateIndex 创建索引（对应 EsIndexManageService.createIndexIfAbsent）
func (c *Client) CreateIndex(ctx context.Context, index string, settings map[string]any) error {
	_, err := c.do(ctx, http.MethodPut, "/"+index, settings)
	return err
}

// IndexExists 判断索引是否存在
func (c *Client) IndexExists(ctx context.Context, index string) (bool, error) {
	raw, err := c.do(ctx, http.MethodHead, "/"+index, nil)
	if err != nil {
		if strings.Contains(err.Error(), "404") {
			return false, nil
		}
		return false, err
	}
	_ = raw
	return true, nil
}

// DeleteDoc 对应 EsQueryService.deleteSnapshotFlow / RestHighLevelClient.delete。
//
// PARITY: 文档不存在时 ES 返回 404，Java 侧同样只打 warn 并继续；
// 这里不把 404 当错误返回，语义与消费者里的"即使不存在也视为成功（幂等）"一致。
func (c *Client) DeleteDoc(ctx context.Context, index, id string) error {
	if c == nil {
		return fmt.Errorf("es: 客户端未初始化")
	}
	if index == "" || id == "" {
		return nil
	}
	if _, err := c.do(ctx, http.MethodDelete, "/"+index+"/_doc/"+id, nil); err != nil {
		if strings.Contains(err.Error(), "404") {
			return nil
		}
		return err
	}
	return nil
}

func parseHits(raw []byte) ([]map[string]any, string, bool, error) {
	var out struct {
		ScrollID string `json:"_scroll_id"`
		Hits     struct {
			Total any `json:"total"`
			Hits  []struct {
				ID     string         `json:"_id"`
				Source map[string]any `json:"_source"`
			} `json:"hits"`
		} `json:"hits"`
	}
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, "", false, fmt.Errorf("es 响应解析失败: %w", err)
	}
	docs := make([]map[string]any, 0, len(out.Hits.Hits))
	for _, h := range out.Hits.Hits {
		src := h.Source
		if src == nil {
			src = map[string]any{}
		}
		src["_id"] = h.ID
		docs = append(docs, src)
	}
	return docs, out.ScrollID, len(docs) == 0, nil
}

func (c *Client) newRequest(ctx context.Context, method, path string, body io.Reader) (*http.Request, error) {
	req, err := http.NewRequestWithContext(ctx, method, c.base+path, body)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	if c.user != "" {
		req.SetBasicAuth(c.user, c.pass)
	}
	return req, nil
}

func (c *Client) do(ctx context.Context, method, path string, body any) ([]byte, error) {
	var rdr io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		rdr = bytes.NewReader(b)
	}
	return c.doRaw(ctx, method, path, rdr, "application/json")
}

func (c *Client) doRaw(ctx context.Context, method, path string, body io.Reader, contentType string) ([]byte, error) {
	req, err := c.newRequest(ctx, method, path, body)
	if err != nil {
		return nil, err
	}
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("es 请求失败 %s %s: %w", method, path, err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 300 {
		return raw, fmt.Errorf("%s", javaESMessage(resp.StatusCode, path, raw))
	}
	return raw, nil
}

// javaESMessage 把 ES 的错误响应体渲染成 Java 客户端抛出的那句原文。
//
// PARITY: 这段文字会被业务层拼进接口响应（如 LargeScaleQueryService 的
// "统计查询异常：" + err），所以它属于响应体的一部分，不是日志。
// Java 侧 elasticsearch-rest-high-client 抛的是 ElasticsearchException，
// toString 固定为 `Elasticsearch exception [type=%s, reason=%s]`；
// Go 之前直接把 HTTP 状态、路径和整段 JSON 贴上去，同一个错误两边文案完全不同。
func javaESMessage(status int, path string, raw []byte) string {
	var parsed struct {
		Error struct {
			Type   string `json:"type"`
			Reason string `json:"reason"`
		} `json:"error"`
	}
	if err := json.Unmarshal(raw, &parsed); err == nil && parsed.Error.Type != "" {
		return fmt.Sprintf("Elasticsearch exception [type=%s, reason=%s]",
			parsed.Error.Type, parsed.Error.Reason)
	}
	// 响应体不是预期的错误 JSON：保留诊断信息，不能把错误变成空字符串
	return fmt.Sprintf("es 返回 %d %s: %s", status, path, truncate(string(raw), 400))
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}
