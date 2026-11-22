package com.ruoyi.base.controller.v3;

import com.ruoyi.base.service.v3.es.CarWarningSearchService;
import com.ruoyi.base.service.v3.query.TrafficQueryException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 大屏实时预警列表（backend → api）。
 *
 * <p>返回裸 JSON 数组，字段与 backend {@code CarWarningInfo} 一致。
 * 索引存在但无数据/索引未创建时返回 200 + 空数组；ES 不可达返回 503，
 * backend 据此回退 Redis 快照。</p>
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/bigscreen")
public class BigScreenWarningV3Controller {

    private final CarWarningSearchService warningSearchService;

    public BigScreenWarningV3Controller(CarWarningSearchService warningSearchService) {
        this.warningSearchService = warningSearchService;
    }

    @GetMapping("/warning/list")
    public ResponseEntity<?> warningList(
            @RequestParam(required = false) String roadCode,
            @RequestParam(required = false) String sectionCode,
            @RequestParam(required = false) String tollCode,
            @RequestParam(required = false) String gantryCode,
            @RequestParam(required = false) String fwqbm,
            @RequestParam(required = false) String escapedType,
            @RequestParam(required = false) String carNo,
            @RequestParam(required = false) String captureType,
            @RequestParam(defaultValue = "100") int limit) {
        try {
            // 兼容旧前端的“抓拍类型哨兵”：type 选中但未选具体编码时，
            // backend 会把哨兵放在 tollCode/gantryCode/fwqbm 位置上。
            List<String> captureTypes = parseCaptureTypes(captureType);
            tollCode = stripCaptureTypeSentinel(tollCode, captureTypes);
            gantryCode = stripCaptureTypeSentinel(gantryCode, captureTypes);
            fwqbm = stripCaptureTypeSentinel(fwqbm, captureTypes);

            List<Map<String, Object>> rows = warningSearchService.search(
                    roadCode, sectionCode, tollCode, gantryCode, fwqbm, escapedType, carNo,
                    captureTypes.isEmpty() ? null : String.join(",", captureTypes), limit);
            return ResponseEntity.ok(rows);
        } catch (TrafficQueryException e) {
            log.warn("[V3预警] 查询失败: {}", e.getMessage());
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("code", e.getCode());
            body.put("message", e.getMessage());
            body.put("data", Collections.emptyList());
            HttpStatus status = HttpStatus.resolve(e.getCode());
            return ResponseEntity.status(status == null ? HttpStatus.INTERNAL_SERVER_ERROR : status).body(body);
        } catch (Exception e) {
            log.error("[V3预警] 未预期异常", e);
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("code", 500);
            body.put("message", "预警列表查询失败");
            body.put("data", Collections.emptyList());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(body);
        }
    }

    /**
     * 提取旧前端哨兵：StationCapture / GantryCapture / ServiceAreaCapture。
     * 其他 token 保留为原维度编码过滤（支持逗号多值）。
     */
    private String stripCaptureTypeSentinel(String value, List<String> captureTypes) {
        if (value == null || value.trim().isEmpty()) {
            return value;
        }
        List<String> keep = new ArrayList<>();
        for (String item : value.split(",")) {
            String token = item == null ? "" : item.trim();
            if (token.isEmpty()) {
                continue;
            }
            if (isCaptureType(token)) {
                addCaptureTypes(captureTypes, token);
            } else {
                keep.add(token);
            }
        }
        return keep.isEmpty() ? null : String.join(",", keep);
    }

    /**
     * 显式 captureType 参数只接受三种哨兵；非法值直接 400，
     * 避免“传错值 -> 不加过滤 -> 返回全量”的静默行为。
     */
    private List<String> parseCaptureTypes(String captureType) {
        List<String> result = new ArrayList<>();
        if (captureType == null || captureType.trim().isEmpty()) {
            return result;
        }
        for (String item : captureType.split(",")) {
            String token = item == null ? "" : item.trim();
            if (token.isEmpty()) {
                continue;
            }
            if (!isCaptureType(token)) {
                throw TrafficQueryException.badRequest(
                        "captureType 非法: " + token
                                + "，允许值: StationCapture/GantryCapture/ServiceAreaCapture");
            }
            if (!result.contains(token)) {
                result.add(token);
            }
        }
        return result;
    }

    private void addCaptureTypes(List<String> captureTypes, String value) {
        if (value == null) {
            return;
        }
        for (String item : value.split(",")) {
            String token = item == null ? "" : item.trim();
            if (isCaptureType(token) && !captureTypes.contains(token)) {
                captureTypes.add(token);
            }
        }
    }

    private boolean isCaptureType(String token) {
        return "StationCapture".equals(token)
                || "GantryCapture".equals(token)
                || "ServiceAreaCapture".equals(token);
    }
}
