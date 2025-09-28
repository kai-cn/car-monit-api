package com.ruoyi.common.config.base;


import lombok.Data;

import java.io.Serializable;

/**
 * @Description: 接口返回数据格式
 * @Author: HuangJun
 * @Date: 2023-09-04 15:59:48
 * @Return
 * @param <T>
 */
@Data
public class Result<T> implements Serializable {

    private static final long serialVersionUID = 1L;

    /**
     * 成功标志
     */
    private boolean success = true;

    /**
     * 返回处理消息
     */
    private String message = "操作成功！";

    /**
     * 返回代码
     */
    private Integer code = 0;

    /**
     * 返回数据对象 data
     */
    private T result;

    /**
     * 时间戳
     */
    private long timestamp = System.currentTimeMillis();

    public Result() {

    }

    /**
     * 兼容VUE3版token失效不跳转登录页面
     *
     * @param code
     * @param message
     */
    public Result(Integer code, String message) {
        this.code = code;
        this.message = message;
    }

    public Result<T> success(String message) {
        this.message = message;
        this.code = 200;
        this.success = true;
        return this;
    }

    public static <T> Result<T> OK() {
        Result<T> r = new Result<T>();
        r.setSuccess(true);
        r.setCode(200);
        r.setMessage("成功");
        return r;
    }

    public static <T> Result<T> OK(String msg) {
        Result<T> r = new Result<T>();
        r.setSuccess(true);
        r.setCode(200);
        r.setMessage(msg);
        return r;
    }

    public static <T> Result<T> OK(T data) {
        Result<T> r = new Result<T>();
        r.setSuccess(true);
        r.setCode(200);
        r.setResult(data);
        return r;
    }

    public static <T> Result<T> OK(String msg, T data) {
        Result<T> r = new Result<T>();
        r.setSuccess(true);
        r.setCode(200);
        r.setMessage(msg);
        r.setResult(data);
        return r;
    }

    public static Result<Object> error(String msg) {
        return error(500, msg);
    }

    public static Result<Object> error(int code, String msg) {
        Result<Object> r = new Result<Object>();
        r.setCode(code);
        r.setMessage(msg);
        r.setSuccess(false);
        return r;
    }

    public static <T> Result<T> error(String msg, T data) {
        Result<T> r = new Result<T>();
        r.setSuccess(false);
        r.setCode(500);
        r.setMessage(msg);
        r.setResult(data);
        return r;
    }

    public static Result<Object> error(int code, String msg, Object data) {
        Result<Object> r = new Result<Object>();
        r.setCode(code);
        r.setMessage(msg);
        r.setResult(data);
        r.setSuccess(false);
        return r;
    }

    public static <T> Result<T> error500(String message) {
        Result<T> r = new Result<T>();
        r.setSuccess(false);
        r.setCode(500);
        r.setMessage(message);
        return r;
    }

    public static Result<Object> error500(Object data) {
        Result<Object> r = new Result<Object>();
        r.setSuccess(false);
        r.setCode(500);
        r.setResult(data);
        return r;
    }
}
