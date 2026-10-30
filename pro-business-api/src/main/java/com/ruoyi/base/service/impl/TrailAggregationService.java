package com.ruoyi.base.service.impl;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.domain.*;
import com.ruoyi.base.service.IOdsSzdnGantryIpService;
import com.ruoyi.base.service.IOdsSzdnSectionService;
import com.ruoyi.base.service.IOdsSzdnTollStationIpService;
import com.ruoyi.base.service.IZdataLocationDictService;
import com.ruoyi.common.utils.CommonUtil;
import com.ruoyi.common.utils.DateUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 轨迹聚合服务
 *
 * 功能说明：
 * 1. 实现轨迹补点算法
 * 2. 轨迹数据清洗和质量评估
 * 3. 轨迹完整性检测
 * 4. 生成轨迹补点后的新版本
 *
 * 设计思路参考文档：
 * - 轨迹拼接逻辑：7天时间差判断新轨迹
 * - 轨迹补点：使用位置字典补全缺失点
 * - 版本管理：同一UUID记录轨迹变化
 */
@Slf4j
@Service
public class TrailAggregationService {

    @Autowired
    private IZdataLocationDictService locationDictService;

    @Autowired
    private IOdsSzdnGantryIpService gantryIpService;

    @Autowired
    private IOdsSzdnTollStationIpService tollStationIpService;

    @Autowired
    private IOdsSzdnSectionService sectionService;

    // ==================== 轨迹补点算法 ====================

    /**
     * 执行轨迹补点
     *
     * 思路：
     * 1. 分析现有轨迹点，识别缺失位置
     * 2. 根据位置字典和路段信息，尝试补全缺失点
     * 3. 生成补点后的新版本轨迹（保持UUID不变）
     *
     * 目的：提升轨迹完整性，支撑逃费分析等业务场景
     *
     * @param originalTrail 原始轨迹
     * @return 补点后的轨迹
     */
    public TrailInfo performTrailFitting(TrailInfo originalTrail) {
        log.info("[轨迹补点] 开始补点：trailUuid={}", originalTrail.getTrailUuid());

        if (originalTrail == null || originalTrail.getTrailList() == null) {
            log.warn("[轨迹补点] 原始轨迹为空，跳过");
            return originalTrail;
        }

        List<TrailBo> originalPoints = originalTrail.getTrailList();
        int originalCount = originalPoints.size();

        // 步骤1：预处理轨迹点，补充位置信息
        List<TrailBo> enrichedPoints = enrichLocationInfo(originalPoints);

        // 步骤2：检测并补全缺失点
        List<TrailBo> fittedPoints = fillMissingPoints(enrichedPoints);

        // 步骤3：重新排序和格式化
        fittedPoints.sort(Comparator.comparing(TrailBo::getCaptureTime));

        // 步骤4：构建新版本轨迹
        TrailInfo newTrail = buildNewTrailVersion(originalTrail, fittedPoints);

        int addedCount = fittedPoints.size() - originalCount;
        log.info("[轨迹补点] 补点完成：trailUuid={}, 原始={}, 补点后={}, 新增={}",
                originalTrail.getTrailUuid(), originalCount, fittedPoints.size(), addedCount);

        return newTrail;
    }

    /**
     * 富集位置信息
     *
     * 思路：根据设备IP查询字典数据，补全经纬度、路段等信息
     * 目的：让轨迹点携带完整的位置属性
     */
    private List<TrailBo> enrichLocationInfo(List<TrailBo> points) {
        // 预加载字典数据
        Map<String, ZdataLocationDict> locationDict = locationDictService.getRedisList();
        Map<String, OdsSzdnGantryIp> gantryIpMap = gantryIpService.selectOdsSzdnGantryIpMap();
        Map<String, OdsSzdnTollStationIp> stationIpMap = tollStationIpService.selectStationIpMap();
        Map<String, OdsSzdnSection> sectionMap = sectionService.getSectionMap();

        return points.stream().map(point -> {
            TrailBo enrichedPoint = JSON.parseObject(JSON.toJSONString(point), TrailBo.class);

            // 尝试通过locationCode查询位置信息
            String locationCode = enrichedPoint.getLocationCode();
            if (CommonUtil.isNotBlank(locationCode)) {
                // 查询位置字典
                ZdataLocationDict location = locationDict.get(locationCode);
                if (location != null) {
                    enrichFromLocationDict(enrichedPoint, location);
                }

                // 查询门架IP
                OdsSzdnGantryIp gantryIp = gantryIpMap.get(locationCode);
                if (gantryIp != null) {
                    enrichFromGantryIp(enrichedPoint, gantryIp, sectionMap);
                }

                // 查询收费站IP
                OdsSzdnTollStationIp stationIp = stationIpMap.get(locationCode);
                if (stationIp != null) {
                    enrichFromStationIp(enrichedPoint, stationIp);
                }
            }

            return enrichedPoint;
        }).collect(Collectors.toList());
    }

    /**
     * 从位置字典富集信息
     */
    private void enrichFromLocationDict(TrailBo point, ZdataLocationDict location) {
        if (point.getLon() == null) {
            point.setLon(location.getLongitude());
        }
        if (point.getLat() == null) {
            point.setLat(location.getLatitude());
        }
        if (CommonUtil.isBlank(point.getRoadCode())) {
            point.setRoadCode(location.getRoadcode());
        }
        if (CommonUtil.isBlank(point.getSectionCode())) {
            point.setSectionCode(location.getSectioncode());
        }
        if (CommonUtil.isBlank(point.getDevName())) {
            point.setDevName(location.getName());
        }
        point.setStandardCode(location.getStandardCode());
    }

    /**
     * 从门架IP信息富集
     */
    private void enrichFromGantryIp(
            TrailBo point, OdsSzdnGantryIp gantryIp, Map<String, OdsSzdnSection> sectionMap) {
        point.setGantryIpBO(gantryIp);
        point.setDevCode(gantryIp.getGantryCode());
        point.setDevName(gantryIp.getGantryName());

        OdsSzdnGantry gantry = gantryIp.getOdsSzdnGantry();
        if (gantry != null) {
            if (point.getLon() == null) {
                point.setLon(new BigDecimal(gantry.getLon()));
            }
            if (point.getLat() == null) {
                point.setLat(new BigDecimal(gantry.getLat()));
            }
            if (CommonUtil.isBlank(point.getRoadCode())) {
                point.setRoadCode(gantry.getRoadCode());
            }
            if (CommonUtil.isBlank(point.getSectionCode())) {
                point.setSectionCode(gantry.getSectionCode());
            }
            if (CommonUtil.isBlank(point.getPileno())) {
                point.setPileno(gantry.getPileNo());
            }
            point.setDirection(String.valueOf(gantry.getDirection()));
            point.setIsVirtual(String.valueOf(gantry.getIsVirtual()));
        }

        point.setLocationFlag("1");
    }

    /**
     * 从收费站IP信息富集
     */
    private void enrichFromStationIp(TrailBo point, OdsSzdnTollStationIp stationIp) {
        point.setStationIpBO(stationIp);
        point.setDevCode(stationIp.getTollCode());
        point.setDevName(stationIp.getTollName());

        OdsSzdnToll toll = stationIp.getOdsSzdnToll();
        if (toll != null) {
            if (point.getLon() == null && CommonUtil.isNotBlank(toll.getLongitude())) {
                point.setLon(new java.math.BigDecimal(toll.getLongitude()));
            }
            if (point.getLat() == null && CommonUtil.isNotBlank(toll.getLatitude())) {
                point.setLat(new java.math.BigDecimal(toll.getLatitude()));
            }
            if (CommonUtil.isBlank(point.getRoadCode())) {
                point.setRoadCode(toll.getRoadCode());
            }
            if (CommonUtil.isBlank(point.getSectionCode())) {
                point.setSectionCode(toll.getSectionCode());
            }
        }

        point.setLocationFlag("1");
    }

    /**
     * 补全缺失点
     *
     * 思路：
     * 1. 分析相邻点之间的路段关系
     * 2. 如果两点在同一路段但距离较远，尝试补点
     * 3. 使用路段上的门架序列进行补全
     *
     * 目的：让轨迹更完整，反映真实行驶路径
     */
    private List<TrailBo> fillMissingPoints(List<TrailBo> points) {
        if (points.size() < 2) {
            return points;
        }

        List<TrailBo> result = new ArrayList<>();
        result.add(points.get(0));

        for (int i = 1; i < points.size(); i++) {
            TrailBo prev = points.get(i - 1);
            TrailBo curr = points.get(i);

            // 添加当前点
            result.add(curr);

            // 检查是否需要补点
            List<TrailBo> fillPoints = tryFillBetween(prev, curr);
            if (fillPoints != null && !fillPoints.isEmpty()) {
                // 将补点插入到合适位置
                result.addAll(result.size() - 1, fillPoints);
            }
        }

        return result;
    }

    /**
     * 尝试在两点之间补点
     */
    private List<TrailBo> tryFillBetween(TrailBo prev, TrailBo curr) {
        List<TrailBo> fillPoints = new ArrayList<>();

        // 检查是否在同一路段
        if (CommonUtil.isBlank(prev.getSectionCode()) || CommonUtil.isBlank(curr.getSectionCode())) {
            return fillPoints;
        }

        if (!prev.getSectionCode().equals(curr.getSectionCode())) {
            return fillPoints;
        }

        // 计算时间差
        Date prevTime = DateUtils.parseDate(prev.getCaptureTime());
        Date currTime = DateUtils.parseDate(curr.getCaptureTime());
        long timeDiff = Math.abs(currTime.getTime() - prevTime.getTime());

        // 时间差超过30分钟，考虑补点
        if (timeDiff > 30 * 60 * 1000L) {
            log.debug("[轨迹补点] 发现可能缺失点：prev={}, curr={}, timeDiff={}min",
                    prev.getPointUuid(), curr.getPointUuid(), timeDiff / 60000);
            // TODO: 这里可以接入路段门架序列，生成虚拟补点
        }

        return fillPoints;
    }

    /**
     * 构建新版本轨迹
     *
     * 思路：保持UUID不变，更新轨迹数据，生成新版本
     * 目的：实现轨迹版本管理，支持数据追溯
     */
    private TrailInfo buildNewTrailVersion(TrailInfo original, List<TrailBo> newPoints) {
        TrailInfo newTrail = new TrailInfo();

        // 复制原轨迹ID（保持不变，实现版本追溯）
        newTrail.setTrailUuid(original.getTrailUuid());

        // 复制并更新轨迹头信息
        ZdataTrailTracks newTracks = JSON.parseObject(
                JSON.toJSONString(original.getTracks()), ZdataTrailTracks.class);

        // 更新点数量
        newTracks.setPointCount((long) newPoints.size());

        // 更新起止时间
        if (!newPoints.isEmpty()) {
            newTracks.setEnterTime(DateUtils.parseDate(newPoints.get(0).getCaptureTime()));
            newTracks.setExitTime(DateUtils.parseDate(newPoints.get(newPoints.size() - 1).getCaptureTime()));
        }

        // 标记为完整轨迹（如果点数足够）
        if (newPoints.size() >= 5) {
            newTracks.setType(1);
        }

        // 更新完整JSON
        newTracks.setTrailPoints(JSON.toJSONString(newPoints));

        newTrail.setTracks(newTracks);
        newTrail.setTrailList(newPoints);

        return newTrail;
    }

    // ==================== 轨迹质量评估 ====================

    /**
     * 评估轨迹质量
     *
     * 思路：从多个维度评估轨迹完整性和可用性
     * 目的：为业务应用提供质量参考
     */
    public TrailQuality assessTrailQuality(TrailInfo trail) {
        TrailQuality quality = new TrailQuality();

        List<TrailBo> points = trail.getTrailList();
        if (points == null || points.isEmpty()) {
            quality.setScore(0);
            quality.setLevel("EMPTY");
            return quality;
        }

        // 点数量评分
        int pointCount = points.size();
        double pointScore = Math.min(1.0, pointCount / 10.0) * 30;

        // 时间跨度评分
        Date firstTime = DateUtils.parseDate(points.get(0).getCaptureTime());
        Date lastTime = DateUtils.parseDate(points.get(points.size() - 1).getCaptureTime());
        long duration = lastTime.getTime() - firstTime.getTime();
        double durationHours = duration / (1000.0 * 60 * 60);
        double durationScore = Math.min(1.0, durationHours / 2.0) * 30;

        // 位置完整度评分
        long locationCompleteCount = points.stream()
                .filter(p -> p.getLon() != null && p.getLat() != null)
                .count();
        double locationScore = (locationCompleteCount * 1.0 / pointCount) * 40;

        // 总分
        double totalScore = pointScore + durationScore + locationScore;
        quality.setScore(totalScore);

        // 质量等级
        if (totalScore >= 90) {
            quality.setLevel("EXCELLENT");
        } else if (totalScore >= 70) {
            quality.setLevel("GOOD");
        } else if (totalScore >= 50) {
            quality.setLevel("FAIR");
        } else {
            quality.setLevel("POOR");
        }

        quality.setPointCount(pointCount);
        quality.setDurationHours(durationHours);
        quality.setLocationCompleteRate(locationCompleteCount * 1.0 / pointCount);

        log.debug("[轨迹质量] 评估完成：score={}, level={}, points={}",
                totalScore, quality.getLevel(), pointCount);

        return quality;
    }

    /**
     * 轨迹质量评估结果
     */
    @lombok.Data
    public static class TrailQuality {
        private double score;
        private String level;
        private int pointCount;
        private double durationHours;
        private double locationCompleteRate;
    }

    // ==================== 轨迹合并处理 ====================

    /**
     * 合并多条轨迹
     *
     * 思路：当发现多条轨迹属于同一辆车的连续行程时，进行合并
     * 目的：还原完整的出行链路
     */
    public TrailInfo mergeTrails(List<TrailInfo> trails) {
        if (trails == null || trails.isEmpty()) {
            return null;
        }

        if (trails.size() == 1) {
            return trails.get(0);
        }

        log.info("[轨迹合并] 开始合并：count={}", trails.size());

        // 收集所有轨迹点
        List<TrailBo> allPoints = trails.stream()
                .filter(t -> t.getTrailList() != null)
                .flatMap(t -> t.getTrailList().stream())
                .sorted(Comparator.comparing(TrailBo::getCaptureTime))
                .collect(Collectors.toList());

        // 创建合并后的轨迹
        TrailInfo mergedTrail = new TrailInfo();
        ZdataTrailTracks mergedTracks = new ZdataTrailTracks();

        // 使用第一条轨迹的UUID
        mergedTracks.setUuid(trails.get(0).getTracks().getUuid());
        mergedTracks.setPlateKey(trails.get(0).getTracks().getPlateKey());

        // 更新时间范围
        mergedTracks.setEnterTime(DateUtils.parseDate(allPoints.get(0).getCaptureTime()));
        mergedTracks.setExitTime(DateUtils.parseDate(allPoints.get(allPoints.size() - 1).getCaptureTime()));
        mergedTracks.setPointCount((long) allPoints.size());
        mergedTracks.setTrailPoints(JSON.toJSONString(allPoints));
        mergedTracks.setType(allPoints.size() >= 5 ? 1 : 0);

        mergedTrail.setTrailUuid(mergedTracks.getUuid());
        mergedTrail.setTracks(mergedTracks);
        mergedTrail.setTrailList(allPoints);

        log.info("[轨迹合并] 合并完成：originalCount={}, mergedPoints={}",
                trails.size(), allPoints.size());

        return mergedTrail;
    }
}
