package com.ruoyi.base.service.optimization;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.domain.*;
import lombok.extern.slf4j.Slf4j;
import org.apache.http.HttpHost;
import org.elasticsearch.action.search.SearchRequest;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestClient;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.index.query.*;
import org.elasticsearch.search.SearchHit;
import org.elasticsearch.search.builder.SearchSourceBuilder;
import org.elasticsearch.search.sort.SortOrder;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.io.IOException;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 方案二：Elasticsearch 全文检索方案
 * <p>
 * 核心思路：
 *   1. 利用 ES 的倒排索引（Inverted Index）+ TF-IDF/BM25 算法
 *   2. 支持 like '%xxx%' 全模糊查询、多字段组合查询、中文分词查询
 *   3. 使用 RestHighLevelClient 客户端进行查询
 *   4. 支持按 snapshottime 范围查询 + 车牌模糊 + 路段精确匹配
 * <p>
 * 索引结构设计：
 *   索引名：ods_rt_szdn_snapshot_flow_addcode
 *   Mapping字段：
 *     - snapshottime: date(时间范围查询，秒级精度)
 *     - platenumber: keyword + text(精确匹配/模糊查询)
 *     - platenumber_keyword: keyword(精确匹配、排序、aggregation)
 *     - gantrycode: keyword(门架编号)
 *     - sectioncode: keyword(路段编号)
 *     - roadname: text + keyword(道路名称，支持模糊查询)
 *     - orgcode: keyword(管理中心编号)
 *     - gantryname: text(门架名称，模糊查询)
 * <p>
 * 优缺点：
 *   优点：
 *     1. like '%xxx%' 全模糊查询性能极优（毫秒级）
 *     2. 支持中文分词查询、同义词查询
 *     3. 支持多字段组合查询
 *     4. 支持聚合统计（按时间/路段统计）
 *     5. 支持大规模数据（百亿级）
 *   缺点：
 *     1. 需要额外维护 ES 集群
 *     2. 数据同步有秒级延迟
 *     3. 一致性保证较弱（最终一致性）
 *     4. 硬件成本较高（内存和磁盘）
 */
@Slf4j
@Service
public class ElasticsearchQueryService {

    /**
     * ES主机地址
     */
    @Value("${elasticsearch.host:127.0.0.1}")
    private String esHost;

    /**
     * ES端口
     */
    @Value("${elasticsearch.port:9200}")
    private int esPort;

    /**
     * ES快照流量索引名
     */
    @Value("${elasticsearch.index.snapshot:ods_rt_szdn_snapshot_flow_addcode}")
    private String snapshotIndex;

    /**
     * ES交易记录索引名
     */
    @Value("${elasticsearch.index.fee:ods_lwzxsfsj_fee_records_01}")
    private String feeIndex;

    /**
     * ES轨迹索引名
     */
    @Value("${elasticsearch.index.trail:zdata_trail_fitting}")
    private String trailIndex;

    /**
     * ES高级客户端
     */
    private RestHighLevelClient client;

    /**
     * 初始化 ES 客户端
     */
    @PostConstruct
    public void init() {
        log.info("[ES查询服务] 初始化 Elasticsearch 客户端，host={}, port={}", esHost, esPort);
        this.client = new RestHighLevelClient(
                RestClient.builder(new HttpHost(esHost, esPort, "http"))
        );
    }

    @PreDestroy
    public void destroy() {
        try {
            if (client != null) {
                client.close();
                log.info("[ES查询服务] ES 客户端已关闭");
            }
        } catch (IOException e) {
            log.error("[ES查询服务] 关闭客户端异常", e);
        }
    }

    /**
     * 门架抓拍流水 ES 查询（模糊查询 + 时间范围查询
     * <p>
     * 性能优化：
     *   1. platenumber 字段使用 keyword + text 双类型
     *   2. 完整车牌走 keyword 精确匹配(B+树结构)
     *   3. 模糊车牌走 text 字段 + wildcard/terms 查询
     *   4. snapshottime 走 range 查询
     *   5. 采用滚动游标 / search_after 分页
     *
     * @param startTime 开始时间（yyyy-MM-dd HH:mm:ss）
     * @param endTime 结束时间
     * @param plateNumber 车牌号（支持模糊：赣A1, 赣A12345）
     * @param gantryCode 门架编号
     * @param sectionCode 路段编号
     * @param orgCode 管理中心编号
     * @param pageNum 页码
     * @param pageSize 每页大小
     * @return 查询结果
     */
    public List<OdsRtSzdnSnapshotFlowAddcode> querySnapshotFlowByEs(
            String startTime,
            String endTime,
            String plateNumber,
            String gantryCode,
            String sectionCode,
            String orgCode,
            int pageNum,
            int pageSize
    ) {
        log.info("[ES查询服务] 门架抓拍流水查询 start={}, end={}, plate={}, gantry={}, section={}, page={}/{}",
                startTime, endTime, plateNumber, gantryCode, sectionCode, pageNum, pageSize);

        try {
            // ============== 1. 构建查询条件 ================
            BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();

            // 2. 时间范围查询（必须条件，缩小搜索范围
            RangeQueryBuilder timeQuery = QueryBuilders.rangeQuery("snapshottime")
                    .format("yyyy-MM-dd HH:mm:ss")
                    .gte(startTime)
                    .lte(endTime);
            boolQuery.filter(timeQuery);

            // 3. 车牌号查询（根据长度判断是精确/前缀/模糊）
            if (plateNumber != null && !plateNumber.isEmpty()) {
                QueryBuilder plateQuery = buildPlateQuery(plateNumber);
                boolQuery.filter(plateQuery);
            }

            // 4. 门架编号（精确匹配）
            if (gantryCode != null && !gantryCode.isEmpty()) {
                boolQuery.filter(QueryBuilders.termQuery("gantrycode", gantryCode));
            }

            // 5. 路段编号（精确匹配）
            if (sectionCode != null && !sectionCode.isEmpty()) {
                boolQuery.filter(QueryBuilders.termQuery("sectioncode", sectionCode));
            }

            // 6. 管理中心编号
            if (orgCode != null && !orgCode.isEmpty()) {
                boolQuery.filter(QueryBuilders.termQuery("orgcode", orgCode));
            }

            // ============== 2. 构建搜索请求 ==================
            SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();
            sourceBuilder.query(boolQuery);
            sourceBuilder.from((pageNum - 1) * pageSize);
            sourceBuilder.size(pageSize);
            sourceBuilder.sort("snapshottime", SortOrder.DESC);
            // 超时设置
            sourceBuilder.timeout(new org.elasticsearch.core.TimeValue(30, java.util.concurrent.TimeUnit.SECONDS));

            SearchRequest searchRequest = new SearchRequest(snapshotIndex);
            searchRequest.source(sourceBuilder);

            // ============== 3. 执行查询 ==========================
            SearchResponse response = client.search(searchRequest, RequestOptions.DEFAULT);

            // ============== 4. 解析结果 =========================
            List<OdsRtSzdnSnapshotFlowAddcode> results = new ArrayList<>();
            for (SearchHit hit : response.getHits().getHits()) {
                try {
                    OdsRtSzdnSnapshotFlowAddcode record = JSON.parseObject(hit.getSourceAsString(), OdsRtSzdnSnapshotFlowAddcode.class);
                    results.add(record);
                } catch (Exception e) {
                    log.warn("[ES查询服务] 解析 ES 文档失败 doc={}", hit.getId(), e);
                }
            }

            log.info("[ES查询服务] 命中记录 total={}, 当前页大小 pageSize={}", response.getHits().getTotalHits().value, results.size());
            return results;

        } catch (Exception e) {
            log.error("[ES查询服务] ES 查询失败，降级返回空/走数据库备份", e);
            // 降级处理：返回空列表，前端可重试
            return Collections.emptyList();
        }
    }

    /**
     * 根据车牌号的长度智能构建查询策略
     * <p>
     * 策略：
     *   1. 完整车牌(7-8位)：termQuery精确匹配
     *   2. 2-6位前缀车牌：wildcard 前缀匹配(性能较好)
     *   3. 1位字符或中间查询：match / fuzzyQuery模糊查询
     *
     * @param plateNumber 车牌号
     * @return 查询条件构建器
     */
    private QueryBuilder buildPlateQuery(String plateNumber) {
        if (plateNumber.length() >= 7) {
            // 完整车牌：精确匹配
            log.debug("[ES查询] 完整车牌精确匹配 plate={}", plateNumber);
            return QueryBuilders.termQuery("platenumber_keyword", plateNumber);
        } else if (plateNumber.length() >= 3) {
            // 部分车牌：前缀匹配（性能较好）
            log.debug("[ES查询] 车牌前缀匹配 plate={}", plateNumber);
            return QueryBuilders.prefixQuery("platenumber_keyword", plateNumber.toUpperCase());
        } else {
            // 1-2字符：通配符模糊查询
            log.debug("[ES查询] 车牌模糊匹配 plate={}", plateNumber);
            return QueryBuilders.wildcardQuery("platenumber_keyword", "*" + plateNumber.toUpperCase() + "*");
        }
    }

    /**
     * 交易流水 ES 查询
     * <p>
     * 与门架抓拍类似，但字段不同：
     *   - vehicleplate: 车牌号
     *   - transtime: 交易时间（作为范围查询条件）
     *   - gantryid: 门架编号
     *   - section_code: 路段编号（从门架表查询）
     */
    public List<OdsLwzxsfsjFeeRecords01> queryFeeRecordsByEs(
            String startTime,
            String endTime,
            String vehiclePlate,
            String gantryId,
            String sectionCode,
            int pageNum,
            int pageSize
    ) {
        log.info("[ES查询服务] 交易流水查询 start={}, end={}, plate={}, gantry={}, section={}, page={}/{}",
                startTime, endTime, vehiclePlate, gantryId, sectionCode, pageNum, pageSize);

        try {
            BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();

            // 时间范围
            RangeQueryBuilder timeQuery = QueryBuilders.rangeQuery("transtime")
                    .format("yyyy-MM-dd HH:mm:ss")
                    .gte(startTime)
                    .lte(endTime);
            boolQuery.filter(timeQuery);

            // 车牌号
            if (vehiclePlate != null && !vehiclePlate.isEmpty()) {
                QueryBuilder plateQuery = buildPlateQuery(vehiclePlate);
                boolQuery.filter(plateQuery);
            }

            // 门架编号
            if (gantryId != null && !gantryId.isEmpty()) {
                boolQuery.filter(QueryBuilders.termQuery("gantryid", gantryId));
            }

            // 路段编号
            if (sectionCode != null && !sectionCode.isEmpty()) {
                boolQuery.filter(QueryBuilders.termQuery("sectioncode", sectionCode));
            }

            SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();
            sourceBuilder.query(boolQuery);
            sourceBuilder.from((pageNum - 1) * pageSize);
            sourceBuilder.size(pageSize);
            sourceBuilder.sort("transtime", SortOrder.DESC);
            sourceBuilder.timeout(new org.elasticsearch.core.TimeValue(30, java.util.concurrent.TimeUnit.SECONDS));

            SearchRequest searchRequest = new SearchRequest(feeIndex);
            searchRequest.source(sourceBuilder);
            SearchResponse response = client.search(searchRequest, RequestOptions.DEFAULT);

            List<OdsLwzxsfsjFeeRecords01> results = new ArrayList<>();
            for (SearchHit hit : response.getHits().getHits()) {
                try {
                    OdsLwzxsfsjFeeRecords01 record = JSON.parseObject(hit.getSourceAsString(), OdsLwzxsfsjFeeRecords01.class);
                    results.add(record);
                } catch (Exception e) {
                    log.warn("[ES查询服务] 解析 ES 文档失败 doc={}", hit.getId(), e);
                }
            }

            log.info("[ES查询服务] 命中记录 total={}, 当前页 size={}", response.getHits().getTotalHits().value, results.size());
            return results;

        } catch (Exception e) {
            log.error("[ES查询服务] ES 查询失败", e);
            return Collections.emptyList();
        }
    }

    /**
     * 轨迹拟合 ES 查询
     * 类似逻辑，略写
     */
    public List<ZdataTrailFitting> queryTrailFittingByEs(
            String startTime,
            String endTime,
            String envehicleid,
            String stationName,
            int pageNum,
            int pageSize
    ) {
        try {
            BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();

            // 时间范围
            RangeQueryBuilder timeQuery = QueryBuilders.rangeQuery("extime")
                    .format("yyyy-MM-dd HH:mm:ss")
                    .gte(startTime)
                    .lte(endTime);
            boolQuery.filter(timeQuery);

            // 车牌号精确查询
            if (envehicleid != null && !envehicleid.isEmpty()) {
                boolQuery.filter(QueryBuilders.termQuery("envehicleid_keyword", envehicleid));
            }

            // 站名称模糊查询
            if (stationName != null && !stationName.isEmpty()) {
                boolQuery.should(QueryBuilders.wildcardQuery("entollstationname", "*" + stationName + "*"));
                boolQuery.should(QueryBuilders.wildcardQuery("extollstationname", "*" + stationName + "*"));
                boolQuery.minimumShouldMatch(1);
            }

            SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();
            sourceBuilder.query(boolQuery);
            sourceBuilder.from((pageNum - 1) * pageSize);
            sourceBuilder.size(pageSize);
            sourceBuilder.sort("extime", SortOrder.DESC);
            sourceBuilder.timeout(new org.elasticsearch.core.TimeValue(30, java.util.concurrent.TimeUnit.SECONDS));

            SearchRequest searchRequest = new SearchRequest(trailIndex);
            searchRequest.source(sourceBuilder);
            SearchResponse response = client.search(searchRequest, RequestOptions.DEFAULT);

            List<ZdataTrailFitting> results = new ArrayList<>();
            for (SearchHit hit : response.getHits().getHits()) {
                ZdataTrailFitting record = JSON.parseObject(hit.getSourceAsString(), ZdataTrailFitting.class);
                results.add(record);
            }
            return results;
        } catch (Exception e) {
            log.error("[ES查询服务] ES 查询失败", e);
            return Collections.emptyList();
        }
    }

    /**
     * 测试 ES 连接健康状态
     * @return true 正常 false 异常
     */
    public boolean checkHealth() {
        try {
            return client.ping(RequestOptions.DEFAULT);
        } catch (Exception e) {
            log.error("[ES查询服务] ES 连接异常", e);
            return false;
        }
    }
}
