package com.ruoyi.base.controller.v3;

import com.ruoyi.base.service.v3.bigscreen.BigScreenStatVo;
import com.ruoyi.base.service.v3.bigscreen.BigScreenStatsService;
import com.ruoyi.base.service.v3.query.TrafficQueryException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 大屏预聚合查询契约（backend → api）。
 *
 * <p>返回裸 JSON（数组/对象），与 backend VO 字段一致；失败返回 4xx/5xx 状态，
 * backend hybrid 模式据此回退 legacy。</p>
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/bigscreen")
public class BigScreenStatsV3Controller {

    private final BigScreenStatsService statsService;

    public BigScreenStatsV3Controller(BigScreenStatsService statsService) {
        this.statsService = statsService;
    }

    @GetMapping("/stats/escape")
    public ResponseEntity<?> escape(
            @RequestParam(required = false) String startDate,
            @RequestParam(required = false) String endDate,
            @RequestParam(required = false) String orgId,
            @RequestParam(required = false) String escapedType) {
        try {
            List<BigScreenStatVo.Escape> rows = statsService.escape(startDate, endDate, orgId, escapedType);
            return ResponseEntity.ok(rows);
        } catch (Exception e) {
            return error("escape", e);
        }
    }

    @GetMapping("/stats/audit")
    public ResponseEntity<?> audit(
            @RequestParam(required = false) String startDate,
            @RequestParam(required = false) String endDate) {
        try {
            BigScreenStatVo.Audit vo = statsService.audit(startDate, endDate);
            return ResponseEntity.ok(vo);
        } catch (Exception e) {
            return error("audit", e);
        }
    }

    @GetMapping("/stats/income")
    public ResponseEntity<?> income(
            @RequestParam(required = false) String queryDateType,
            @RequestParam(required = false) String startDate,
            @RequestParam(required = false) String applyTime1,
            @RequestParam(required = false) String applyTime2) {
        try {
            List<BigScreenStatVo.Income> rows = statsService.income(
                    queryDateType, startDate, applyTime1, applyTime2);
            return ResponseEntity.ok(rows);
        } catch (Exception e) {
            return error("income", e);
        }
    }

    @GetMapping("/stats/warning-top")
    public ResponseEntity<?> warningTop(
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime,
            @RequestParam(defaultValue = "10") int topN) {
        try {
            List<BigScreenStatVo.WarningTop> rows = statsService.warningTop(startTime, endTime, topN);
            return ResponseEntity.ok(rows);
        } catch (Exception e) {
            return error("warningTop", e);
        }
    }

    private ResponseEntity<?> error(String endpoint, Exception e) {
        int code = 500;
        String message = "大屏预聚合查询失败";
        if (e instanceof TrafficQueryException) {
            code = ((TrafficQueryException) e).getCode();
            message = e.getMessage();
        } else {
            log.error("[V3大屏] {} 未预期异常", endpoint, e);
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("code", code);
        body.put("message", message);
        body.put("data", Collections.emptyList());
        HttpStatus status = HttpStatus.resolve(code);
        return ResponseEntity.status(status == null ? HttpStatus.INTERNAL_SERVER_ERROR : status).body(body);
    }
}
