package com.ruoyi.base.service.v3.query;

/**
 * V3 查询异常：携带对外的 HTTP/业务码（400 参数错误、503 ES 不可用）。
 */
public class TrafficQueryException extends RuntimeException {

    private final int code;

    public TrafficQueryException(int code, String message) {
        super(message);
        this.code = code;
    }

    public TrafficQueryException(int code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
    }

    public int getCode() {
        return code;
    }

    public static TrafficQueryException badRequest(String message) {
        return new TrafficQueryException(400, message);
    }

    public static TrafficQueryException unavailable(String message) {
        return new TrafficQueryException(503, message);
    }

    public static TrafficQueryException unavailable(String message, Throwable cause) {
        return new TrafficQueryException(503, message, cause);
    }
}
