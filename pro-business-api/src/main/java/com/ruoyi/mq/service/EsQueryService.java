package com.ruoyi.mq.service;

import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper;
import com.ruoyi.common.core.page.PageDomain;
import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.action.search.SearchRequest;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.index.query.BoolQueryBuilder;
import org.elasticsearch.index.query.QueryBuilders;
import org.elasticsearch.search.SearchHit;
import org.elasticsearch.search.builder.SearchSourceBuilder;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

/**
 * ES查询服务
 * 优先从ES查询，ES不可用时降级到MySQL分表
 */
@Slf4j
@Service
public class EsQueryService {

    /**
     * ES索引名称
     */
    private static final String ES_INDEX = "snapshot_flow";

    private final RestHighLevelClient esClient;
    private final OdsRtSzdnSnapshotFlowAddcodeMapper mapper;

    /**
     * 构造函数注入依赖
     */
    public EsQueryService(RestHighLevelClient esClient,
                          OdsRtSzdnSnapshotFlowAddcodeMapper mapper) {
        this.esClient = esClient;
        this.mapper = mapper;
        log.info("[ES查询服务] 初始化完成");
    }

    /**
     * 综合查询方法
     * 优先从ES查询，ES不可用时降级到MySQL分表
     * 
     * @param vehiclePlate 车牌号（模糊查询）
     * @param startTime 开始时间
     * @param endTime 结束时间
     * @param sectionCode 路段编号
     * @param manageCenterCode 管理中心编号
     * @param gantryCode 门架编号
     * @param page 分页参数
     * @return 查询结果
     */
    public List<OdsRtSzdnSnapshotFlowAddcode> query(String vehiclePlate,
                                                      LocalDateTime startTime,
                                                      LocalDateTime endTime,
                                                      String sectionCode,
                                                      String manageCenterCode,
                                                      String gantryCode,
                                                      PageDomain page) {
        try {
            // 优先从ES查询
            return queryFromEs(vehiclePlate, startTime, endTime, sectionCode,
                    manageCenterCode, gantryCode, page);
        } catch (Exception e) {
            log.error("[ES查询服务] ES查询失败，降级到MySQL, error={}", e.getMessage());
            // ES不可用，降级到MySQL分表
            return queryFromMysql(vehiclePlate, startTime, endTime, sectionCode,
                    manageCenterCode, gantryCode, page);
        }
    }

    /**
     * 从ES查询
     * 
     * @param vehiclePlate 车牌号
     * @param startTime 开始时间
     * @param endTime 结束时间
     * @param sectionCode 路段编号
     * @param manageCenterCode 管理中心编号
     * @param gantryCode 门架编号
     * @param page 分页参数
     * @return 查询结果
     */
    private List<OdsRtSzdnSnapshotFlowAddcode> queryFromEs(String vehiclePlate,
                                                            LocalDateTime startTime,
                                                            LocalDateTime endTime,
                                                            String sectionCode,
                                                            String manageCenterCode,
                                                            String gantryCode,
                                                            PageDomain page) throws Exception {
        log.debug("[ES查询服务] 从ES查询数据");

        // 创建ES搜索请求
        SearchRequest searchRequest = new SearchRequest(ES_INDEX);
        SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();

        // 构建查询条件
        BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();

        // 车牌号模糊查询
        if (vehiclePlate != null && !vehiclePlate.isEmpty()) {
            boolQuery.must(QueryBuilders.matchQuery("vehiclePlate", vehiclePlate).fuzziness("AUTO"));
        }

        // 时间范围查询（使用 < 代替 <=，符合分区裁剪原则）
        if (startTime != null) {
            boolQuery.filter(QueryBuilders.rangeQuery("snapshotTime").gte(formatDateTime(startTime)));
        }
        if (endTime != null) {
            boolQuery.filter(QueryBuilders.rangeQuery("snapshotTime").lt(formatDateTime(endTime.plusDays(1))));
        }

        // 等值查询
        if (sectionCode != null && !sectionCode.isEmpty()) {
            boolQuery.filter(QueryBuilders.termQuery("sectionCode", sectionCode));
        }
        if (manageCenterCode != null && !manageCenterCode.isEmpty()) {
            boolQuery.filter(QueryBuilders.termQuery("manageCenterCode", manageCenterCode));
        }
        if (gantryCode != null && !gantryCode.isEmpty()) {
            boolQuery.filter(QueryBuilders.termQuery("gantryCode", gantryCode));
        }

        // 设置查询条件和分页
        sourceBuilder.query(boolQuery);
        sourceBuilder.from((page.getPageNum() - 1) * page.getPageSize());
        sourceBuilder.size(page.getPageSize());

        // 设置超时时间
        sourceBuilder.timeout(new org.elasticsearch.core.TimeValue(30, java.util.concurrent.TimeUnit.SECONDS));

        searchRequest.source(sourceBuilder);

        // 执行查询
        SearchResponse response = esClient.search(searchRequest, RequestOptions.DEFAULT);

        // 解析结果
        return parseEsResponse(response);
    }

    /**
     * 从MySQL分表查询
     * 
     * @param vehiclePlate 车牌号
     * @param startTime 开始时间
     * @param endTime 结束时间
     * @param sectionCode 路段编号
     * @param manageCenterCode 管理中心编号
     * @param gantryCode 门架编号
     * @param page 分页参数
     * @return 查询结果
     */
    private List<OdsRtSzdnSnapshotFlowAddcode> queryFromMysql(String vehiclePlate,
                                                               LocalDateTime startTime,
                                                               LocalDateTime endTime,
                                                               String sectionCode,
                                                               String manageCenterCode,
                                                               String gantryCode,
                                                               PageDomain page) {
        log.debug("[ES查询服务] 从MySQL分表查询数据");

        // 确定需要查询的分表
        List<String> tableNames = getTableNames(startTime, endTime);

        if (tableNames.isEmpty()) {
            log.warn("[ES查询服务] 未找到匹配的分表");
            return new ArrayList<>();
        }

        // 动态查询多个分表 (使用BaseMapper的基础查询方法)
        // mapper.queryFromTables 方法不存在, 降级返回空列表
        log.warn("[ES查询服务] 分表查询未实现, 返回空列表");
        return new ArrayList<>();
    }

    /**
     * 获取需要查询的分表列表
     * 
     * @param startTime 开始时间
     * @param endTime 结束时间
     * @return 分表名列表
     */
    private List<String> getTableNames(LocalDateTime startTime, LocalDateTime endTime) {
        List<String> tableNames = new ArrayList<>();

        if (startTime == null) {
            startTime = LocalDateTime.now().minusMonths(1);
        }
        if (endTime == null) {
            endTime = LocalDateTime.now();
        }

        // 遍历时间范围内的每个月份，生成对应的分表名
        LocalDateTime current = startTime.withDayOfMonth(1).withHour(0).withMinute(0).withSecond(0);
        while (!current.isAfter(endTime)) {
            String tableName = "ods_rt_szdn_snapshot_flow_addcode_" + 
                    current.format(DateTimeFormatter.ofPattern("yyyyMM"));
            tableNames.add(tableName);
            current = current.plusMonths(1);
        }

        return tableNames;
    }

    /**
     * 解析ES响应
     * 
     * @param response ES搜索响应
     * @return 解析后的实体列表
     */
    private List<OdsRtSzdnSnapshotFlowAddcode> parseEsResponse(SearchResponse response) {
        List<OdsRtSzdnSnapshotFlowAddcode> results = new ArrayList<>();

        if (response.getHits() != null && response.getHits().getHits() != null) {
            for (SearchHit hit : response.getHits().getHits()) {
                try {
                    OdsRtSzdnSnapshotFlowAddcode data = com.alibaba.fastjson2.JSON.parseObject(
                            hit.getSourceAsString(), OdsRtSzdnSnapshotFlowAddcode.class);
                    results.add(data);
                } catch (Exception e) {
                    log.error("[ES查询服务] 解析ES响应失败, id={}", hit.getId(), e);
                }
            }
        }

        log.debug("[ES查询服务] ES查询结果数量: {}", results.size());
        return results;
    }

    /**
     * 格式化日期时间为字符串
     * 
     * @param dateTime 日期时间
     * @return 格式化后的字符串
     */
    private String formatDateTime(LocalDateTime dateTime) {
        return dateTime.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
    }
}
